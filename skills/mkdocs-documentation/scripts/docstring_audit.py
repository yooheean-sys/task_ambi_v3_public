"""docstring の棚卸し（4 粒度の有無と、Args/Returns/Raises の節・項目説明の欠落）。

ruff の pydocstyle（D1xx）が見るのは docstring の**有無**だけで、
Args/Returns の節や Pydantic の項目説明の
欠落は見ない。mkdocstrings で描くと、それらは「説明の無い引数・項目」として並ぶ。

    # 全体の集計。対象の src は --src の明示 → mkdocs.yml の mkdocstrings の paths
    # → 自動探索 の順に決める
    python docstring_audit.py summary [--src DIR ...] [--exclude-module ui]
    # ファイルごとの作業一覧（直す前に読む）
    python docstring_audit.py todo FILE ...

数えるのは公開の名前だけ（`_` で始まる名前・
モジュールは mkdocstrings の `filters: ["!^_"]` で描かれない）。
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

SECTION = {
    "args": re.compile(r"^\s*(Args|Arguments|Parameters):\s*$", re.M),
    "returns": re.compile(r"^\s*(Returns|Yields):\s*$", re.M),
    "raises": re.compile(r"^\s*Raises:\s*$", re.M),
    "attributes": re.compile(r"^\s*Attributes:\s*$", re.M),
}
SKIP_DIRS = {".venv", "venv", "node_modules", ".git", "site", "__pycache__", "tests"}


def discover_src(root: Path) -> list[Path]:
    """パッケージを含む `src` ディレクトリを探す。

    Args:
        root: リポジトリルート。

    Returns:
        直下にパッケージ（`__init__.py` を持つディレクトリ）がある `src` の一覧（パス順）。
    """
    found: list[Path] = []
    for src in sorted(root.glob("**/src")):
        if any(part in SKIP_DIRS or part.startswith(".") for part in src.relative_to(root).parts):
            continue
        if any((child / "__init__.py").is_file() for child in src.iterdir() if child.is_dir()):
            found.append(src)
    return found


def load_mkdocs_config(path: Path) -> dict:
    """`mkdocs.yml` を読む（`!ENV`・`!!python/name` などの独自タグは値を捨てて読み飛ばす）。

    Args:
        path: `mkdocs.yml` のパス。

    Returns:
        設定の辞書。ファイルが無いか読めなければ空。
    """
    if not path.is_file():
        return {}
    try:
        import yaml  # noqa: PLC0415  # mkdocs の依存として入っている（docs グループ）
    except ImportError:
        return {}

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("", lambda loader, suffix, node: None)
    _Loader.add_multi_constructor("tag:yaml.org,2002:python/", lambda loader, suffix, node: None)
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader) or {}  # noqa: S506  # 独自タグを捨てる安全なローダ


def targets_from_mkdocs(config: dict) -> tuple[list[str], list[str]]:
    """`mkdocs.yml` から mkdocstrings の `paths` と除外モジュールを取り出す。

    Args:
        config: `load_mkdocs_config` の戻り。

    Returns:
        `(src の一覧, 除外モジュール名の一覧)`。設定が無ければ空。
    """
    paths: list[str] = []
    for plugin in config.get("plugins") or []:
        if isinstance(plugin, dict) and "mkdocstrings" in plugin:
            handlers = (plugin["mkdocstrings"] or {}).get("handlers") or {}
            paths = list(((handlers.get("python") or {}).get("paths")) or [])
    extra = ((config.get("extra") or {}).get("docs_build")) or {}
    return paths, list(extra.get("exclude_modules") or [])


def iter_files(src_roots: list[Path], excluded: set[str]) -> Iterator[Path]:
    """公開モジュールのファイルを列挙する（private と除外モジュールは飛ばす）。

    Args:
        src_roots: `src` ディレクトリの一覧。
        excluded: 除外するモジュール名（ファイル名の stem）。

    Yields:
        対象の `.py` ファイル。
    """
    for src in src_roots:
        for path in sorted(src.rglob("*.py")):
            parts = path.relative_to(src).with_suffix("").parts
            if any(p.startswith("_") and p != "__init__" for p in parts):
                continue
            if parts[-1] in excluded:
                continue
            yield path


def decorators(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """デコレータの名前を集める。

    Args:
        fn: 関数定義。

    Returns:
        デコレータの末尾の名前（`property`・`overload` など）。
    """
    out: set[str] = set()
    for d in fn.decorator_list:
        node = d.func if isinstance(d, ast.Call) else d
        if isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.Name):
            out.add(node.id)
    return out


def params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """`self`・`cls` を除いた引数名を署名順に返す。

    Args:
        fn: 関数定義。

    Returns:
        引数名の一覧（`*args`・`**kwargs` を含む）。
    """
    a = fn.args
    names = [x.arg for x in [*a.posonlyargs, *a.args]]
    if a.vararg:
        names.append(a.vararg.arg)
    names += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        names.append(a.kwarg.arg)
    return [n for n in names if n not in ("self", "cls")]


def returns_value(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """戻り値の注釈が `None` 以外か。

    Args:
        fn: 関数定義。

    Returns:
        値を返す注釈なら `True`。
    """
    r = fn.returns
    if r is None or (isinstance(r, ast.Constant) and r.value is None):
        return False
    return not (isinstance(r, ast.Name) and r.id in ("None", "NoReturn", "Never"))


def own_raises(fn: ast.AST) -> bool:
    """関数本体（入れ子の関数・クラスを除く）に `raise X` があるか。

    Args:
        fn: 関数定義。

    Returns:
        例外を送出する文があれば `True`（素の `raise` は数えない）。
    """
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(n, ast.Raise) and n.exc is not None:
            return True
        stack.extend(ast.iter_child_nodes(n))
    return False


def _has_attr_doc(body: list[ast.stmt], i: int) -> bool:
    nxt = body[i + 1] if i + 1 < len(body) else None
    return (
        isinstance(nxt, ast.Expr)
        and isinstance(nxt.value, ast.Constant)
        and isinstance(nxt.value.value, str)
    )


def analyze(path: Path) -> list[tuple[str, int, str, str]]:
    """1 ファイルの欠落を列挙する。

    Args:
        path: 対象のファイル。

    Returns:
        `(種別, 行, 名前, 詳細)` の一覧。種別は module・class・func:nodoc・args・returns・raises・
        attr。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rows: list[tuple[str, int, str, str]] = []
    if ast.get_docstring(tree) is None:
        kind = "package" if path.name == "__init__.py" else "module"
        rows.append((kind, 1, path.name, "docstring なし"))

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                doc = ast.get_docstring(node)
                if doc is None:
                    rows.append(("class", node.lineno, prefix + node.name, "docstring なし"))
                doc = doc or ""
                for i, st in enumerate(node.body):
                    if not (isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)):
                        continue
                    name = st.target.id
                    ann = ast.unparse(st.annotation)
                    if name.startswith("_") or "ClassVar" in ann or name == "model_config":
                        continue
                    in_section = SECTION["attributes"].search(doc) and re.search(
                        rf"^\s*{re.escape(name)}\b.*:", doc, re.M
                    )
                    if _has_attr_doc(node.body, i) or in_section:
                        continue
                    value = f" = {ast.unparse(st.value)}" if st.value is not None else ""
                    rows.append(("attr", st.lineno, f"{prefix}{node.name}.{name}", f"{ann}{value}"))
                visit(node.body, prefix + node.name + ".")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_") and node.name not in ("__init__", "__call__"):
                    continue
                deco = decorators(node)
                if "overload" in deco:
                    continue
                qual = prefix + node.name
                doc = ast.get_docstring(node)
                if doc is None:
                    if node.name != "__init__":
                        rows.append(("func:nodoc", node.lineno, qual, "docstring なし"))
                    continue
                is_prop = bool(deco & {"property", "cached_property", "computed_field"})
                is_validator = bool(deco & {"field_validator", "model_validator", "validator"})
                ps = params(node)
                if ps and not is_prop and not SECTION["args"].search(doc):
                    rows.append(("args", node.lineno, qual, ", ".join(ps)))
                if (
                    returns_value(node)
                    and not is_prop
                    and node.name != "__init__"
                    and not SECTION["returns"].search(doc)
                ):
                    rows.append(("returns", node.lineno, qual, ast.unparse(node.returns)))  # type: ignore[arg-type]
                if own_raises(node) and not is_validator and not SECTION["raises"].search(doc):
                    rows.append(("raises", node.lineno, qual, ""))

    visit(tree.body, "")
    return rows


def cmd_summary(args: argparse.Namespace) -> int:
    """全体の集計を表示する。

    Args:
        args: コマンドライン引数。

    Returns:
        終了コード（欠落が 1 件でもあれば 1）。
    """
    root = Path(args.root).resolve()
    excluded = set(args.exclude_module)
    if args.src:
        srcs, origin = [root / s for s in args.src], "--src"
    else:
        paths, mk_excluded = targets_from_mkdocs(load_mkdocs_config(root / "mkdocs.yml"))
        if paths:
            srcs, origin = [root / p for p in paths], "mkdocs.yml"
            excluded |= set(mk_excluded)
        else:
            srcs, origin = (
                discover_src(root),
                "自動探索（凍結物や画面が混ざりうるので --src で絞る）",
            )
    print(f"対象 src（{origin}）:", ", ".join(str(s.relative_to(root)) for s in srcs) or "（無し）")
    if excluded:
        print("除外モジュール:", ", ".join(sorted(excluded)))
    total: Counter[str] = Counter()
    per_file: Counter[str] = Counter()
    for path in iter_files(srcs, excluded):
        for kind, *_ in analyze(path):
            total[kind] += 1
            per_file[str(path.relative_to(root))] += 1
    labels = {
        "package": "パッケージ docstring なし",
        "module": "モジュール docstring なし",
        "class": "クラス docstring なし",
        "func:nodoc": "関数 docstring なし",
        "args": "Args 節の欠落",
        "returns": "Returns 節の欠落",
        "raises": "Raises 節の欠落",
        "attr": "項目（属性）の説明の欠落",
    }
    for key, label in labels.items():
        print(f"{label}: {total[key]}")
    if per_file:
        print("\n欠落の多いファイル:")
        for name, n in per_file.most_common(args.top):
            print(f"  {n:4} {name}")
    return 1 if sum(total.values()) else 0


def cmd_todo(args: argparse.Namespace) -> int:
    """ファイルごとの作業一覧を表示する。

    Args:
        args: コマンドライン引数。

    Returns:
        終了コード（常に 0）。
    """
    for name in args.files:
        rows = analyze(Path(name))
        if not rows:
            continue
        print(f"### {name}")
        for kind, line, qual, detail in rows:
            print(f"  {kind:10} L{line:<5} {qual}  {detail}"[:200])
    return 0


def main() -> int:
    """コマンドラインの入口。

    Returns:
        終了コード。
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary", help="全体の集計")
    s.add_argument("--root", default=".")
    s.add_argument("--src", action="append", default=[], help="対象の src（繰り返し可）")
    s.add_argument("--exclude-module", action="append", default=[], help="除外するモジュール名")
    s.add_argument("--top", type=int, default=30)
    s.set_defaults(func=cmd_summary)
    t = sub.add_parser("todo", help="ファイルごとの作業一覧")
    t.add_argument("files", nargs="+")
    t.set_defaults(func=cmd_todo)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
