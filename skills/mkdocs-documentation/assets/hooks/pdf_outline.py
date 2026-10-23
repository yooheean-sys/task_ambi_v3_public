"""MkDocs の hook: 一括 PDF にナビの階層どおりのしおり（ブックマーク）を付ける。

mkdocs-exporter の aggregator はページごとの PDF をナビの順につなぐだけで、しおりを作らない
（指南書の PDF 確認項目 1「しおりと見出し階層」を満たさない）。exporter が一括 PDF を保存した
後に、各ページの PDF のページ数をナビの順に足し上げて、節とページのしおりを付ける。

一括 PDF が作られなかったビルド（`ENABLE_PDF_EXPORT` 無し）では何もしない。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mkdocs.plugins import event_priority, get_plugin_logger
from mkdocs.structure.nav import Navigation
from pypdf import PdfReader, PdfWriter

DEFAULT_PDF_OUTPUT = "pdf/site.pdf"
"""一括 PDF の出力先の既定（`extra.docs_build.pdf_output` が無いとき）。"""

log = get_plugin_logger(__name__)
_state: dict[str, Navigation] = {}


def _pdf_pages(page: Any) -> int | None:  # noqa: ANN401  # mkdocs の Page（exporter が属性を足す）
    """一括 PDF に入るページ数（exporter がそのページについて記録した値）。

    Args:
        page: ナビのページ。

    Returns:
        ページ数。PDF にならなかったページは `None`。
    """
    formats: dict[str, dict[str, int]] = getattr(page, "formats", {})
    pdf = formats.get("pdf")
    if pdf is None:
        return None
    return pdf["pages"] - pdf.get("skipped_pages", 0)


@event_priority(-100)
def on_nav(nav: Navigation, **kwargs: Any) -> Navigation:  # noqa: ANN401  # mkdocs の hook の署名
    """ナビを控える（しおりの階層に使う）。

    Args:
        nav: 組み立て済みのナビ。
        **kwargs: MkDocs が渡すその他の引数（使わない）。

    Returns:
        受け取ったナビ（変更しない）。
    """
    _state["nav"] = nav
    return nav


@event_priority(-98)  # exporter が一括 PDF を保存した（-95）後、後始末（-100）の前
def on_post_build(config: Any, **kwargs: Any) -> None:  # noqa: ANN401  # mkdocs の hook の署名
    """一括 PDF にしおりを付けて書き直す。

    Args:
        config: MkDocs の設定（`site_dir` と `extra.docs_build.pdf_output` を読む）。
        **kwargs: MkDocs が渡すその他の引数（使わない）。
    """
    nav = _state.get("nav")
    settings = (config.get("extra") or {}).get("docs_build") or {}
    path = Path(config["site_dir"]) / (settings.get("pdf_output") or DEFAULT_PDF_OUTPUT)
    if nav is None or not path.is_file() or all(_pdf_pages(p) is None for p in nav.pages):
        return

    starts: dict[int, int] = {}
    offset = 0
    for page in nav.pages:  # exporter と同じくナビの順に平たく並べたページ
        count = _pdf_pages(page)
        if count is None:
            continue
        starts[id(page)] = offset
        offset += count

    reader = PdfReader(path)
    if offset != len(reader.pages):
        log.warning(
            "しおりを付けられない: ページ数の合計 %d が一括 PDF の %d と合わない",
            offset,
            len(reader.pages),
        )
        return

    writer = PdfWriter(clone_from=reader)

    def first_start(item: Any) -> int | None:  # noqa: ANN401  # Page か Section
        if item.is_page:
            return starts.get(id(item))
        for child in item.children or []:
            found = first_start(child)
            if found is not None:
                return found
        return None

    def add(items: list[Any], parent: Any = None) -> None:  # noqa: ANN401  # pypdf の outline 項目
        for item in items:
            start = first_start(item)
            if start is None:
                continue
            node = writer.add_outline_item(item.title or "", start, parent=parent)
            if item.is_section:
                add(item.children, node)

    add(nav.items)
    writer.page_mode = "/UseOutlines"
    writer.write(path)
    log.info("一括 PDF にしおりを付けた: %s（%d ページ）", path, offset)
