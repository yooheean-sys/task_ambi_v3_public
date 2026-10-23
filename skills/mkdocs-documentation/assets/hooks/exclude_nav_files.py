"""MkDocs の hook: literate-nav のナビ定義（`SUMMARY.md`）をページとしてビルドしない。

literate-nav はナビ定義を「ナビに出さない」扱いにするだけで、ページとしては描いてしまう
（`site/api/SUMMARY/` などができ、一括 PDF にも混ざりうる）。literate-nav が `on_files`
（優先度 -100）でナビを読み終えた後に、ビルド対象から外す。
"""

from __future__ import annotations

from typing import Any

from mkdocs.plugins import event_priority
from mkdocs.structure.files import Files, InclusionLevel

NAV_FILE = "SUMMARY.md"
"""literate-nav のナビ定義のファイル名（`mkdocs.yml` の `nav_file` と同じ）。"""


@event_priority(-200)
def on_files(files: Files, **kwargs: Any) -> Files:  # noqa: ANN401  # mkdocs の hook の署名
    """ナビ定義のファイルをビルド対象から外す。

    Args:
        files: ビルド対象のファイル一覧。
        **kwargs: MkDocs が渡すその他の引数（使わない）。

    Returns:
        ナビ定義を除外扱いにしたファイル一覧（同じオブジェクト）。
    """
    for file in files:
        if file.name == NAV_FILE.removesuffix(".md") and file.src_uri.endswith(NAV_FILE):
            file.inclusion = InclusionLevel.EXCLUDED
    return files
