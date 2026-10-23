"""FastAPI アプリの OpenAPI スキーマを JSON にダンプする。

MkDocs の REST API ページ（neoteroi）が読む中間成果物を作る。待受は開始しない（`app.openapi()` は
lifespan を起動しない）。`hooks/gen_openapi.py` がビルドの前に別プロセスでこのスクリプトを呼ぶ。
手で呼ぶ場合は次のとおり。

    uv run python scripts/dump_openapi.py --app api:create_app --output docs/openapi/openapi.json

`--app` は `module:attr`。`attr` が `openapi()` を持てば FastAPI インスタンスとして、
そうでなければアプリ工場として呼んでから使う。アプリの組み立てが外部の設定（`.env` など）
を要るなら、その環境でしか動かない。内容が前回と同じなら書き込まない
（`mkdocs serve` の監視が再ビルドを繰り返さないため）。
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
from pathlib import Path


def load_app(target: str) -> object:
    """`module:attr` からアプリを得る。

    Args:
        target: `module:attr` の形の指定。

    Returns:
        `openapi()` を持つアプリ。`attr` がアプリ工場なら呼んだ結果。

    Raises:
        ValueError: 指定の形が `module:attr` でない。
    """
    module_name, sep, attr = target.partition(":")
    if not sep or not attr:
        msg = f"--app は module:attr の形で指定する: {target!r}"
        raise ValueError(msg)
    obj = getattr(importlib.import_module(module_name), attr)
    return obj if hasattr(obj, "openapi") else obj()


def render_schema(target: str) -> str:
    """アプリを組み立てて OpenAPI スキーマを JSON 文字列にする（組み立て中のログは抑止する）。

    Args:
        target: `module:attr` の形のアプリの指定。

    Returns:
        整形済みの OpenAPI スキーマ（UTF-8 のまま・字下げ 2・末尾改行つき）。
    """
    logging.disable(logging.CRITICAL)
    try:
        schema = load_app(target).openapi()  # type: ignore[attr-defined]
    finally:
        logging.disable(logging.NOTSET)
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    """スキーマをダンプ先へ書く（内容が同じなら書かない）。"""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--app", required=True, help="module:attr（アプリ工場か FastAPI インスタンス）"
    )
    parser.add_argument("--output", default="docs/openapi/openapi.json", help="ダンプ先")
    args = parser.parse_args()
    output = Path(args.output)
    text = render_schema(args.app)
    if output.is_file() and output.read_text(encoding="utf-8") == text:
        print(f"unchanged {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
