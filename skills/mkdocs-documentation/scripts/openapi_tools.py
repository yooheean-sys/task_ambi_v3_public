"""FastAPI の OpenAPI（REST API ドキュメントの元）の棚卸し・記載・正本との突き合わせの道具。

プロジェクトの venv で、リポジトリルートから呼ぶ（アプリを import できる必要がある）。

    python openapi_tools.py audit --app api:create_app
        summary・パラメータ・項目・応答の説明の欠落と、描画を壊す書式（行頭 #・<占位子>・[..][..]）
        を数える
    python openapi_tools.py components-map --app api:create_app [--out map.json]
        components の型名 → 定義クラス（module:qualname）の対応表
    python openapi_tools.py add-flag --app api:create_app [FILE ...]
        components に載るモデルの model_config に use_attribute_docstrings=True を足す
        （属性 docstring を項目説明にする）
    python openapi_tools.py transcribe --spec docs/design/openapi.yaml FILE ...
        正本の summary・成功応答の説明を、router の `operation_id="X",` 行の直後へ転記する
    python openapi_tools.py compare --app api:create_app --spec docs/design/openapi.yaml
        生成スキーマと正本を操作単位で突き合わせる
    uv run --with openapi-spec-validator python openapi_tools.py validate --app api:create_app
        生成スキーマが OpenAPI の仕様として妥当か（描画ツールが読めるか）

`--app` は `module:attr`（attr が `openapi()` を持てばアプリ、そうでなければアプリ工場として呼ぶ）。
アプリの組み立て中のログは抑止する。
"""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import json
import logging
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

PLACEHOLDER = re.compile(r"<[A-Za-z_/][^>\s]*>")
REFERENCE = re.compile(r"\[[^\]\n]+\]\[[^\]\n]*\]")
METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


def load_app(target: str) -> Any:  # noqa: ANN401  # FastAPI に依存しない
    """`module:attr` からアプリを得る（組み立て中のログは抑止する）。

    Args:
        target: `module:attr`。

    Returns:
        `openapi()` を持つアプリ。

    Raises:
        ValueError: 指定の形が `module:attr` でない。
    """
    module_name, sep, attr = target.partition(":")
    if not sep or not attr:
        msg = f"--app は module:attr の形で指定する: {target!r}"
        raise ValueError(msg)
    sys.path.insert(0, str(Path.cwd()))
    logging.disable(logging.CRITICAL)
    try:
        obj = getattr(importlib.import_module(module_name), attr)
        return obj if hasattr(obj, "openapi") else obj()
    finally:
        logging.disable(logging.NOTSET)


def load_spec(path: Path) -> dict[str, Any]:
    """正本（OpenAPI の YAML か JSON）を読む。

    Args:
        path: 正本のパス。

    Returns:
        OpenAPI 文書。
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    import yaml  # noqa: PLC0415  # mkdocs の依存として入っている

    return yaml.safe_load(text)


def operations(doc: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """`(パス, メソッド)` → 操作。

    Args:
        doc: OpenAPI 文書。

    Returns:
        操作の辞書。
    """
    return {
        (path, method): op
        for path, item in doc.get("paths", {}).items()
        for method, op in item.items()
        if method in METHODS
    }


def resolve(doc: dict[str, Any], obj: dict[str, Any]) -> dict[str, Any]:
    """`$ref` を 1 段だけ解決する。

    Args:
        doc: OpenAPI 文書。
        obj: `$ref` を持ちうる値。

    Returns:
        参照先（`$ref` が無ければそのまま）。
    """
    ref = obj.get("$ref")
    if not ref:
        return obj
    node: Any = doc
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def _outside_code(text: str) -> str:
    return re.sub(r"`[^`]*`", "", text)


def cmd_audit(args: argparse.Namespace) -> int:
    """生成スキーマの説明の欠落と、描画を壊す書式を数える。

    Args:
        args: コマンドライン引数。

    Returns:
        終了コード（問題があれば 1）。
    """
    doc = load_app(args.app).openapi()
    counts: Counter[str] = Counter()
    lines: list[str] = []
    info = doc.get("info", {})
    if not info.get("description"):
        lines.append("info.description が無い（FastAPI(description=...)）")
    if not doc.get("tags"):
        lines.append("トップレベルの tags（openapi_tags）が無い（タグの説明が出ない）")
    for (path, method), op in operations(doc).items():
        label = f"{method.upper()} {path}"
        counts["operations"] += 1
        if (op.get("summary") or "").isascii():
            counts["summary_auto"] += 1
            lines.append(f"{label}: summary が関数名からの自動生成（{op.get('summary')!r}）")
        description = op.get("description") or ""
        if not description:
            counts["no_description"] += 1
            lines.append(f"{label}: description（関数 docstring）が無い")
        if re.match(r"\s*#", description):
            counts["heading"] += 1
            lines.append(f"{label}: description が # で始まる（Python-Markdown で h1 になる）")
        for key in ("summary", "description"):
            if PLACEHOLDER.search(_outside_code(op.get(key) or "")):
                counts["placeholder"] += 1
                lines.append(f"{label}: {key} に <占位子>（HTML タグとして消える）")
        for p in op.get("parameters", []):
            if not p.get("description"):
                counts["param_nodesc"] += 1
                lines.append(f"{label}: 引数 {p['name']} に説明が無い")
        for resp in op.get("responses", {}).values():
            desc = resp.get("description", "")
            if desc in ("Successful Response", "Validation Error", "") or desc.isascii():
                counts["response_default"] += 1
    for name, schema in doc.get("components", {}).get("schemas", {}).items():
        if name in ("HTTPValidationError", "ValidationError"):
            continue
        if not schema.get("description"):
            counts["schema_nodesc"] += 1
            lines.append(f"schema {name}: 型の説明が無い")
        if "__" in name or name.endswith(("-Input", "-Output")):
            counts["mangled_name"] += 1
            lines.append(f"schema {name}: 機械的な型名（同名クラスの衝突・入出力の分割）")
        for prop_name, prop in (schema.get("properties") or {}).items():
            desc = prop.get("description") or ""
            if not desc:
                counts["prop_nodesc"] += 1
                lines.append(f"schema {name}.{prop_name}: 項目の説明が無い")
            elif PLACEHOLDER.search(desc):
                counts["placeholder"] += 1
                lines.append(f"schema {name}.{prop_name}: 説明に <占位子>（neoteroi の表で消える）")
    for line in lines[: args.limit]:
        print(line)
    if len(lines) > args.limit:
        print(f"…ほか {len(lines) - args.limit} 件")
    print("集計:", dict(counts))
    print(
        "（応答の説明が既定の英語のもの:",
        counts["response_default"],
        "件。FastAPI 自動の 422 は除けない）",
    )
    problems = sum(v for k, v in counts.items() if k not in ("operations", "response_default"))
    return 1 if problems or lines else 0


def component_classes(app: Any) -> dict[str, list[str]]:  # noqa: ANN401
    """OpenAPI の components の型名 → 定義クラス（`module:qualname`）。

    Args:
        app: アプリ。

    Returns:
        型名ごとの候補（1 件なら確定）。
    """
    from pydantic import BaseModel  # noqa: PLC0415

    comps = app.openapi().get("components", {}).get("schemas", {})

    def subclasses(cls: type) -> list[type]:
        out: list[type] = []
        for sub in cls.__subclasses__():
            out.append(sub)
            out.extend(subclasses(sub))
        return out

    candidates: dict[str, list[type]] = {}
    for cls in set(subclasses(BaseModel)):
        if cls.__module__.startswith(("pydantic", "fastapi", "starlette")):
            continue
        candidates.setdefault(cls.__name__, []).append(cls)
        mangled = f"{cls.__module__.replace('.', '__')}__{cls.__qualname__}"
        candidates.setdefault(mangled, []).append(cls)
    return {
        name: sorted({f"{c.__module__}:{c.__qualname__}" for c in candidates.get(name, [])})
        for name in comps
    }


def cmd_components_map(args: argparse.Namespace) -> int:
    """OpenAPI の components の対応表を表示（または保存）する。

    Args:
        args: コマンドライン引数。

    Returns:
        終了コード（常に 0）。
    """
    mapping = component_classes(load_app(args.app))
    text = json.dumps(mapping, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    for name, hits in mapping.items():
        if len(hits) != 1:
            print("未確定:", name, hits)
    print(f"型 {len(mapping)} 件（確定 {sum(len(v) == 1 for v in mapping.values())}）")
    return 0


def module_file(module: str) -> Path | None:
    """モジュール名からソースファイルを得る。

    Args:
        module: ドット区切りのモジュール名。

    Returns:
        ソースファイルのパス。得られなければ `None`。
    """
    spec = importlib.util.find_spec(module)
    return Path(spec.origin) if spec and spec.origin else None


def cmd_add_flag(args: argparse.Namespace) -> int:
    """OpenAPI の型 に載るモデルの `model_config` に `use_attribute_docstrings=True` を足す。

    Args:
        args: コマンドライン引数。

    Returns:
        終了コード（常に 0）。
    """
    mapping = component_classes(load_app(args.app))
    targets: dict[Path, set[str]] = {}
    for hits in mapping.values():
        for hit in hits:
            module, qual = hit.split(":")
            path = module_file(module)
            if path is not None:
                targets.setdefault(path.resolve(), set()).add(qual)
    only = {Path(f).resolve() for f in args.files}
    for path, quals in sorted(targets.items()):
        if only and path not in only:
            continue
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        lines = src.split("\n")
        edits: list[tuple[int, int, bool]] = []
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.ClassDef) and node.name in {q.split(".")[-1] for q in quals}
            ):
                continue
            cfg = next(
                (
                    st
                    for st in node.body
                    if isinstance(st, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "model_config" for t in st.targets)
                ),
                None,
            )
            if cfg is None:
                print(
                    f"model_config が無い（親の設定を継承するか確かめる）: {path.name}:{node.name}"
                )
                continue
            if "use_attribute_docstrings" in ast.unparse(cfg) or not isinstance(
                cfg.value, ast.Call
            ):
                continue
            call = cfg.value
            edits.append(
                (call.end_lineno or 0, call.end_col_offset or 0, bool(call.args or call.keywords))
            )
        for ln, col, has_args in sorted(edits, reverse=True):
            line = lines[ln - 1]
            ins = ", use_attribute_docstrings=True" if has_args else "use_attribute_docstrings=True"
            lines[ln - 1] = line[: col - 1] + ins + line[col - 1 :]
        if edits:
            path.write_text("\n".join(lines), encoding="utf-8")
        print(f"{path}: {len(edits)} 件")
    return 0


def _dwidth(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _literal(indent: str, key: str, text: str, width: int) -> list[str]:
    one = f"{indent}{key}={json.dumps(text, ensure_ascii=False)},"
    if _dwidth(one) <= width:
        return [one]
    inner = indent + "    "
    budget = width - _dwidth(inner) - 2
    out = [f"{indent}{key}=("]
    rest = text
    while rest:
        used, cut, last_break = 0, len(rest), -1
        for i, ch in enumerate(rest):
            used += _dwidth(ch)
            if used > budget:
                cut = i
                break
            if ch in " 、。・）」，":
                last_break = i + 1
        if cut < len(rest) and last_break > cut * 0.5:
            cut = last_break
        out.append(f"{inner}{json.dumps(rest[:cut], ensure_ascii=False)}")
        rest = rest[cut:]
    out.append(f"{indent}),")
    return out


def cmd_transcribe(args: argparse.Namespace) -> int:
    """正本の summary・成功応答の説明を router へ転記する。

    Args:
        args: コマンドライン引数。

    Returns:
        終了コード（正本に無い operationId があれば 1）。
    """
    spec = load_spec(Path(args.spec))
    ops = {op["operationId"]: op for op in operations(spec).values() if "operationId" in op}
    missing: list[str] = []
    for name in args.files:
        path = Path(name)
        lines = path.read_text(encoding="utf-8").split("\n")
        out: list[str] = []
        done = 0
        for i, line in enumerate(lines):
            out.append(line)
            m = re.match(r'^(\s*)operation_id="(\w+)",\s*$', line)
            if not m:
                continue
            indent, op_id = m.group(1), m.group(2)
            following = "\n".join(lines[i + 1 : i + 4])
            if "summary=" in following:
                continue
            op = ops.get(op_id)
            if op is None:
                missing.append(op_id)
                continue
            if op.get("summary"):
                out += _literal(indent, "summary", op["summary"], args.width)
            success = next(
                (
                    resolve(spec, r).get("description")
                    for c, r in op.get("responses", {}).items()
                    if str(c).startswith("2")
                ),
                None,
            )
            if success:
                out += _literal(indent, "response_description", success, args.width)
            done += 1
        path.write_text("\n".join(out), encoding="utf-8")
        print(f"{path}: {done} 操作に転記")
    if missing:
        print("正本に無い operationId:", missing)
    return 1 if missing else 0


def cmd_compare(args: argparse.Namespace) -> int:
    """生成スキーマと正本を操作単位で突き合わせる。

    Args:
        args: コマンドライン引数。

    Returns:
        終了コード（差があれば 1）。
    """
    gen = load_app(args.app).openapi()
    spec = load_spec(Path(args.spec))
    g_ops, s_ops = operations(gen), operations(spec)
    problems: list[str] = []
    for key in sorted(set(s_ops) - set(g_ops)):
        problems.append(f"正本にあるが生成に無い: {key}")
    for key in sorted(set(g_ops) - set(s_ops)):
        problems.append(f"生成にあるが正本に無い: {key}")
    for key in sorted(set(g_ops) & set(s_ops)):
        g, s = g_ops[key], s_ops[key]
        label = f"{key[1].upper()} {key[0]}"
        for field in ("operationId", "summary", "tags"):
            if s.get(field) is not None and g.get(field) != s.get(field):
                problems.append(
                    f"{label}: {field} が違う（生成 {g.get(field)!r}・正本 {s.get(field)!r}）"
                )
        path_vars = set(re.findall(r"{(\w+)}", key[0]))
        s_params = {resolve(spec, p)["name"] for p in s.get("parameters", [])}
        for p in g.get("parameters", []):
            if p["in"] != "path" and p["name"] not in s_params:
                problems.append(
                    f"{label}: 正本に無い {p['in']} 引数 {p['name']!r}（依存注入の誤読の疑い）"
                )
            if p["in"] == "path" and p["name"] not in path_vars:
                problems.append(f"{label}: パスに無い path 引数 {p['name']}")
        if bool(s.get("requestBody")) != bool(g.get("requestBody")):
            problems.append(f"{label}: requestBody の有無が違う")
        for code, s_resp in s.get("responses", {}).items():
            s_resp = resolve(spec, s_resp)
            g_resp = g.get("responses", {}).get(str(code))
            if g_resp is None:
                problems.append(f"{label}: 正本の応答 {code} が生成に無い")
                continue
            if s_resp.get("content") and not (g_resp.get("content") or {}).get(
                "application/json", {}
            ).get("schema"):
                problems.append(f"{label}: 応答 {code} の本文スキーマが生成に無い")
            if s_resp.get("headers") and not g_resp.get("headers"):
                problems.append(f"{label}: 応答 {code} のヘッダが生成に無い")
        for code in g.get("responses", {}):
            if code not in {str(c) for c in s.get("responses", {})} and code != "422":
                problems.append(f"{label}: 生成にだけある応答 {code}")
    print(f"操作: 生成 {len(g_ops)}・正本 {len(s_ops)}")
    for p in problems:
        print("  ", p)
    print("差:", len(problems))
    return 1 if problems else 0


def cmd_validate(args: argparse.Namespace) -> int:
    """生成スキーマを OpenAPI の仕様で検証する（openapi-spec-validator が要る）。

    Args:
        args: コマンドライン引数。

    Returns:
        終了コード（妥当でなければ 1、検証器が無ければ 2）。
    """
    try:
        from openapi_spec_validator import validate  # noqa: PLC0415
    except ImportError:
        print("openapi-spec-validator が無い。uv run --with openapi-spec-validator で呼ぶ")
        return 2
    schema = load_app(args.app).openapi()
    try:
        validate(schema)
    except Exception as exc:  # noqa: BLE001  # 検証器の例外の型は版で変わる
        print("妥当でない:", str(exc)[:2000])
        return 1
    print(f"OpenAPI {schema.get('openapi')} として妥当（操作 {len(operations(schema))}）")
    return 0


def main() -> int:
    """コマンドラインの入口。

    Returns:
        終了コード。
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit")
    a.add_argument("--app", required=True)
    a.add_argument("--limit", type=int, default=80, help="表示する行数の上限")
    a.set_defaults(func=cmd_audit)
    m = sub.add_parser("components-map")
    m.add_argument("--app", required=True)
    m.add_argument("--out")
    m.set_defaults(func=cmd_components_map)
    f = sub.add_parser("add-flag")
    f.add_argument("--app", required=True)
    f.add_argument("files", nargs="*", help="対象を絞るファイル（省略時は全部）")
    f.set_defaults(func=cmd_add_flag)
    t = sub.add_parser("transcribe")
    t.add_argument("--spec", required=True)
    t.add_argument("--width", type=int, default=100)
    t.add_argument("files", nargs="+")
    t.set_defaults(func=cmd_transcribe)
    c = sub.add_parser("compare")
    c.add_argument("--app", required=True)
    c.add_argument("--spec", required=True)
    c.set_defaults(func=cmd_compare)
    v = sub.add_parser("validate")
    v.add_argument("--app", required=True)
    v.set_defaults(func=cmd_validate)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
