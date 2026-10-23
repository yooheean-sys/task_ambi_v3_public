"""docstring への Google style 節の挿入と、属性 docstring の挿入を行う道具。

使い方（リポジトリルートで）:
    python doctool.py SPEC.py [--root .] [--width 100] [--dry]

`--dry` は書き込まずに差分だけを表示する。spec の書き方は references/docstring-spec.md を参照。

spec.py は次の 2 つの dict を任意に定義する。

    FUNCS = {"<repo 相対パス>": {"<qualname>": {"args": {"p": "説明"}, "returns": "説明"}}}
    ATTRS = {"<repo 相対パス>": {"<クラス qualname>": {"field": "説明"}}}

`args` は既存の Args 節が無いときだけ足す（引数の過不足は検査して止める）。`returns`／`yields`
も節が無いときだけ足す。挿入位置は Google style の順（Args → Returns/Yields → その他）。
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path.cwd()
WIDTH = 100
HEADER = re.compile(
    r"^(Args|Arguments|Returns|Yields|Raises|Attributes|Examples?|Notes?|Warns|Warnings?|"
    r"See Also|Todo|References|Other Parameters|Keyword Args|Methods):\s*$"
)


def dwidth(s: str) -> int:
    """全角を幅 2、半角を幅 1 として表示幅を数える。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def wrap(first_prefix: str, cont_prefix: str, text: str, last_suffix: str = "") -> list[str]:
    """幅 WIDTH に収まるよう折り返す。空白・句読点の直後で切る（無ければ文字単位）。"""
    out: list[str] = []
    prefix = first_prefix
    rest = text
    while True:
        budget = WIDTH - dwidth(prefix)
        if dwidth(rest) + dwidth(last_suffix) <= budget:
            out.append(prefix + rest + last_suffix)
            return out
        # budget 内で最後の切れ目を探す
        w = 0
        cut = -1
        hard = 0
        for i, ch in enumerate(rest):
            w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
            if w > budget:
                break
            hard = i + 1
            if ch in " 、。・）」』】，" or (
                i + 1 < len(rest) and rest[i + 1] in "（「『【" and ch != " "
            ):
                cut = i + 1
        if cut <= 0 or cut < hard * 0.5:
            cut = hard
        line = rest[:cut].rstrip()
        out.append(prefix + line)
        rest = rest[cut:].lstrip(" ")
        prefix = cont_prefix
        if not rest:
            if last_suffix:
                out[-1] += last_suffix
            return out


def load_spec(path: Path) -> tuple[dict, dict]:
    """Spec ファイルを読み込み、`FUNCS` と `ATTRS` を返す。

    spec と同じフォルダを import の探索先に足すので、spec から別の spec を import できる。

    Args:
        path: spec ファイル。

    Returns:
        `(FUNCS, ATTRS)`。定義されていなければ空の辞書。
    """
    sys.path.insert(0, str(path.resolve().parent))
    spec = importlib.util.spec_from_file_location("spec", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "FUNCS", {}), getattr(mod, "ATTRS", {})


def find_def(tree: ast.Module, qual: str) -> ast.AST:
    """`A.b` の形の修飾名から関数・クラスの定義を探す（overload は最後の定義を採る）。"""
    parts = qual.split(".")
    body = tree.body
    node: ast.AST | None = None
    for p in parts:
        found = None
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == p:
                # overload は飛ばし、本体（最後の定義）を採る
                found = n
        if found is None:
            raise KeyError(qual)
        node = found
        body = found.body  # type: ignore[attr-defined]
    assert node is not None
    return node


def param_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """`self`・`cls` を除いた引数名を署名順に返す。"""
    a = fn.args
    names = [x.arg for x in [*a.posonlyargs, *a.args, *a.kwonlyargs]]
    if a.vararg:
        names.insert(len(a.posonlyargs) + len(a.args), a.vararg.arg)
    if a.kwarg:
        names.append(a.kwarg.arg)
    return [n for n in names if n not in ("self", "cls")]


def entry_name(fn: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> str:
    """Args 節での表記（`*args`・`**kwargs` は星を付ける）。"""
    if fn.args.vararg and fn.args.vararg.arg == name:
        return "*" + name
    if fn.args.kwarg and fn.args.kwarg.arg == name:
        return "**" + name
    return name


def section_lines(header: str, entries: list[tuple[str | None, str]], ind: str) -> list[str]:
    """節（Args・Returns など）の行を組み立てる。"""
    lines = [ind + header + ":"]
    for name, desc in entries:
        if name is None:
            lines += wrap(ind + "    ", ind + "    ", desc)
        else:
            lines += wrap(ind + "    " + name + ": ", ind + "        ", desc)
    return lines


def patch_func(lines: list[str], fn: ast.AST, spec: dict, where: str) -> list[str]:
    """関数の docstring に、無い節（Args・Returns/Yields）だけを Google style の順で足す。"""
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)), where
    first = fn.body[0]
    if not (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        raise ValueError(f"{where}: docstring が無い")
    s, e = first.lineno - 1, first.end_lineno - 1  # type: ignore[operator]
    col = first.col_offset
    ind = " " * col
    raw = lines[s : e + 1]
    doc = first.value.value
    has_args = re.search(r"^\s*(Args|Arguments):\s*$", doc, re.M)
    has_ret = re.search(r"^\s*(Returns|Yields):\s*$", doc, re.M)

    new_args: list[str] = []
    new_ret: list[str] = []
    if "args" in spec and not has_args:
        params = param_names(fn)
        given = spec["args"]
        missing = [p for p in params if p not in given]
        extra = [p for p in given if p not in params]
        if missing or extra:
            raise ValueError(f"{where}: args 不一致 missing={missing} extra={extra}")
        new_args = section_lines("Args", [(entry_name(fn, p), given[p]) for p in params], ind)
    for key, header in (("returns", "Returns"), ("yields", "Yields")):
        if key in spec and not has_ret:
            new_ret = section_lines(header, [(None, spec[key])], ind)
    if not new_args and not new_ret:
        return lines

    opener = raw[0][col:]
    m = re.match(r'^([rRuU]?)("""|\'\'\')', opener)
    if not m:
        raise ValueError(f"{where}: docstring の開始が三重引用符でない: {opener!r}")
    q = m.group(2)
    pre = raw[0][: col + len(m.group(0))]
    if s == e:
        # 1 行 docstring
        body_text = raw[0][col + len(m.group(0)) :]
        assert body_text.endswith(q), where
        summary = body_text[: -len(q)]
        content = [pre + summary]
        tail_after = ""
    else:
        content = list(raw)
        last = content[-1]
        if last.strip() != q:
            # `...文末。"""` の形 → 閉じ引用符を独立行へ
            idx = last.rfind(q)
            content[-1] = last[:idx].rstrip()
        else:
            content = content[:-1]
        tail_after = ""

    # content = 開き行〜閉じ前の本文行。節見出しの位置を探す
    def is_header(line: str) -> str | None:
        if not line.startswith(ind) or line[len(ind) : len(ind) + 1] == " ":
            return None
        mm = HEADER.match(line[len(ind) :])
        return mm.group(1) if mm else None

    header_idx = [
        (i, is_header(line_)) for i, line_ in enumerate(content) if i > 0 and is_header(line_)
    ]

    def insert_block(content: list[str], at: int, block: list[str]) -> list[str]:
        before = content[:at]
        after = content[at:]
        while before and before[-1].strip() == "" and len(before) > 1:
            before.pop()
        res = before + [""] + block
        if after:
            res += [""] + after
        return res

    if new_args:
        at = header_idx[0][0] if header_idx else len(content)
        content = insert_block(content, at, new_args)
        header_idx = [
            (i, is_header(line_)) for i, line_ in enumerate(content) if i > 0 and is_header(line_)
        ]
    if new_ret:
        after_args = [i for i, h in header_idx if h not in ("Args", "Arguments")]
        # Args 節より後ろで、Args 以外の最初の見出しの前
        args_pos = [i for i, h in header_idx if h in ("Args", "Arguments")]
        cand = [i for i in after_args if not args_pos or i > args_pos[0]]
        at = cand[0] if cand else len(content)
        content = insert_block(content, at, new_ret)
    # 末尾の空行を落として閉じる
    while content and content[-1].strip() == "" and len(content) > 1:
        content.pop()
    content.append(ind + q + tail_after)
    # 末尾空白の除去（空行は完全に空にする）
    content = [line_.rstrip() for line_ in content]
    return lines[:s] + content + lines[e + 1 :]


def patch_attrs(lines: list[str], cls: ast.AST, spec: dict[str, str], where: str) -> list[str]:
    """クラスの項目の直後に属性 docstring を足す（既にあれば止める）。"""
    assert isinstance(cls, ast.ClassDef), where
    targets: list[tuple[int, int, str]] = []
    body = cls.body
    seen = set()
    for i, st in enumerate(body):
        if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
            name = st.target.id
        elif (
            isinstance(st, ast.Assign)
            and len(st.targets) == 1
            and isinstance(st.targets[0], ast.Name)
        ):
            name = st.targets[0].id
        else:
            continue
        if name not in spec:
            continue
        nxt = body[i + 1] if i + 1 < len(body) else None
        if (
            isinstance(nxt, ast.Expr)
            and isinstance(nxt.value, ast.Constant)
            and isinstance(nxt.value.value, str)
        ):
            raise ValueError(f"{where}.{name}: 既に属性 docstring がある")
        targets.append((st.end_lineno, st.col_offset, name))  # type: ignore[arg-type]
        seen.add(name)
    missing = set(spec) - seen
    if missing:
        raise ValueError(f"{where}: 項目が見つからない {sorted(missing)}")
    for end, col, name in sorted(targets, reverse=True):
        ind = " " * col
        text = spec[name]
        one = f'{ind}"""{text}"""'
        fits = dwidth(one) <= WIDTH
        block = [one] if fits else wrap(ind + '"""', ind, text, last_suffix='"""')
        # 既存の流儀: 属性 docstring の後に空行を置いて次の項目へ
        if end < len(lines) and lines[end].strip():
            block = [*block, ""]
        lines = lines[:end] + block + lines[end:]
    return lines


def main() -> None:
    """コマンドラインの入口。"""
    import argparse  # noqa: PLC0415

    global ROOT, WIDTH  # noqa: PLW0603  # 道具の設定（行幅・ルート）を引数で差し替える
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", help="FUNCS／ATTRS を定義した spec ファイル")
    parser.add_argument("--root", default=".", help="spec のパスの起点（リポジトリルート）")
    parser.add_argument(
        "--width", type=int, default=100, help="行幅（ruff の line-length。全角は幅 2）"
    )
    parser.add_argument("--dry", action="store_true", help="書き込まずに差分を表示する")
    args = parser.parse_args()
    ROOT, WIDTH = Path(args.root).resolve(), args.width
    spec_path = Path(args.spec)
    dry = args.dry
    funcs, attrs = load_spec(spec_path)
    files = sorted(set(funcs) | set(attrs))
    for rel in files:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        # 下から順に当てるため、対象ごとに再解析する
        jobs: list[tuple[str, str, dict]] = [("f", q, s) for q, s in funcs.get(rel, {}).items()]
        jobs += [("a", q, s) for q, s in attrs.get(rel, {}).items()]
        # 行番号の降順で処理
        tree = ast.parse("\n".join(lines))
        order = sorted(jobs, key=lambda j: find_def(tree, j[1]).lineno, reverse=True)  # type: ignore[attr-defined]
        for kind, qual, s in order:
            tree = ast.parse("\n".join(lines))
            node = find_def(tree, qual)
            where = f"{rel}:{qual}"
            if kind == "f":
                lines = patch_func(lines, node, s, where)
            else:
                lines = patch_attrs(lines, node, s, where)
        new = "\n".join(lines)
        ast.parse(new)
        if dry:
            import difflib

            sys.stdout.writelines(
                difflib.unified_diff(text.splitlines(True), new.splitlines(True), rel, rel, n=1)
            )
        else:
            path.write_text(new, encoding="utf-8")
            print("patched", rel, len(jobs))


if __name__ == "__main__":
    main()
