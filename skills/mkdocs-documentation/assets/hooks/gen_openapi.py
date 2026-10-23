"""MkDocs の hook: ビルドの前に `scripts/dump_openapi.py` で OpenAPI スキーマをダンプする。

アプリの指定とダンプ先は `mkdocs.yml` の `extra.docs_build.openapi_app`・`openapi_output` から読む。
指南書（A1.1 手順 5）は同じプロセスで import して呼ぶが、ここでは**別プロセス**で呼ぶ。
アプリの組み立てがログの設定（ルートロガの差し替え）や重い import を伴うと、mkdocs の
プロセスを汚すためである。
別プロセスなので、`mkdocs serve` 中のコード変更も再ビルドのたびに反映される。

環境変数 `SKIP_OPENAPI_DUMP` を設定するとダンプを飛ばす（既存の `openapi.json` を使う）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mkdocs.exceptions import PluginError


def on_pre_build(config: Any, **kwargs: Any) -> None:  # noqa: ANN401  # mkdocs の hook の署名
    """ビルドの前に OpenAPI スキーマをダンプする。

    Args:
        config: MkDocs の設定（`extra.docs_build` と設定ファイルの所在を読む）。
        **kwargs: MkDocs が渡すその他の引数（使わない）。

    Raises:
        PluginError: ダンプに失敗した（アプリを組み立てられない環境など）。
    """
    settings = (config.get("extra") or {}).get("docs_build") or {}
    app = settings.get("openapi_app") or ""
    if not app or os.environ.get("SKIP_OPENAPI_DUMP"):
        return
    root = Path(config["config_file_path"]).resolve().parent
    output = settings.get("openapi_output") or "docs/openapi/openapi.json"
    result = subprocess.run(  # noqa: S603  # 実行するのはリポジトリ内の固定スクリプトだけ
        [
            sys.executable,
            str(root / "scripts" / "dump_openapi.py"),
            "--app",
            app,
            "--output",
            output,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = (
            "OpenAPI スキーマのダンプに失敗した（アプリを組み立てられる環境か確認する。"
            f"既存の openapi.json で続けるなら SKIP_OPENAPI_DUMP=1）:\n{result.stderr[-2000:]}"
        )
        raise PluginError(msg)
