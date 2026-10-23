"""MkDocs の hook: 本文の `<key>` のような占位子が HTML タグとして消えないようにする。

設計文書（md・CSV）や OpenAPI の summary は、`projects/<key>/agents.yaml`・`<PROFILE>` の
形で占位子を書く。Markdown はこれを HTML タグとして扱い、ブラウザは中身ごと表示しない。
元の文書（GitHub・Obsidian でも読む正本）は書き換えず、描画の直前に `&lt;…&gt;` へ置き換える。

- `extra.docs_build.escape_all_prefixes` のページ（生の HTML を使わない設計文書）は、
  `<br>`（table-reader がセル内の改行に使う）以外の `<名前>` をすべてエスケープする。
  `<area>`・`<body>`・`<title>` のように HTML の要素名と同じ占位子もあるため、要素名では
  判定しない。正規表現の文字クラス `[A-Z][A-Z0-9_]*` は参照リンク `[…][…]` と解釈され、
  autorefs が警告を出すので、角括弧もエスケープする。
- `extra.docs_build.escape_non_html_prefixes` のページ（neoteroi が生の HTML を差し込む
  REST API）は、HTML の要素名でない `<名前>` だけをエスケープする。
- コードフェンスとインラインコードの中は触らない。
- 他のプラグイン（read_csv・include-markdown・neoteroi）が本文を差し込んだ後に動かすため、
  優先度を最後にする。
"""

from __future__ import annotations

import re
from typing import Any

from mkdocs.plugins import event_priority

HTML_ELEMENTS = frozenset(
    (  # noqa: SIM905  # 要素名を 1 行ずつ並べると 100 行を超えるため
        "a abbr address area article aside audio b bdi bdo blockquote body br "
        "button canvas caption cite code col colgroup data datalist dd del "
        "details dfn dialog div dl dt em embed fieldset figcaption figure "
        "footer form h1 h2 h3 h4 h5 h6 head header hr html i iframe img input "
        "ins kbd label legend li link main map mark meta meter nav noscript "
        "object ol optgroup option output p param picture pre progress q rp rt "
        "ruby s samp script section select small source span strong style sub "
        "summary sup svg table tbody td template textarea tfoot th thead time "
        "title tr track u ul var video wbr"
    ).split(" ")
)
"""生の HTML を差し込むページで残す要素名（これ以外の `<名前>` を占位子とみなす）。"""

ALL_ESCAPE_KEEP = frozenset({"br"})
"""生の HTML を使わないページで残す要素名（table-reader がセル内の改行に使う `<br>` だけ）。"""

_FENCE = re.compile(r"^(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^(?P=fence)[ \t]*$", re.M | re.S)
_INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
_TAG = re.compile(r"<(/?)([A-Za-z_][^<>\s/]*)>")
_REFERENCE = re.compile(r"\[([^\]\n]+)\]\[([^\]\n]*)\]")


def _escape_text(text: str, *, keep: frozenset[str], escape_references: bool) -> str:
    """コードの外の本文だけをエスケープする。

    Args:
        text: コードフェンスを含まない本文の断片。
        keep: 残す要素名（小文字）。
        escape_references: `[…][…]` の角括弧もエスケープするか。

    Returns:
        占位子（と必要なら参照リンク風の角括弧）をエスケープした本文。
    """

    def escape_segment(segment: str) -> str:
        segment = _TAG.sub(
            lambda m: (
                m.group(0) if m.group(2).lower() in keep else f"&lt;{m.group(1)}{m.group(2)}&gt;"
            ),
            segment,
        )
        if escape_references:
            segment = _REFERENCE.sub(r"\\[\1\\]\\[\2\\]", segment)
        return segment

    parts: list[str] = []
    last = 0
    for match in _INLINE_CODE.finditer(text):
        parts.append(escape_segment(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(escape_segment(text[last:]))
    return "".join(parts)


@event_priority(-100)
def on_page_markdown(markdown: str, page: Any, config: Any, **kwargs: Any) -> str:  # noqa: ANN401  # mkdocs の hook の署名
    """対象ページで、占位子の山括弧をエスケープする。

    Args:
        markdown: 他のプラグインが処理した後のページの Markdown。
        page: 対象のページ。
        config: MkDocs の設定（`extra.docs_build` の対象接頭辞を読む）。
        **kwargs: MkDocs が渡すその他の引数（使わない）。

    Returns:
        エスケープ後の Markdown（対象外のページはそのまま）。
    """
    settings = (config.get("extra") or {}).get("docs_build") or {}
    all_prefixes = tuple(settings.get("escape_all_prefixes") or ())
    html_prefixes = tuple(settings.get("escape_non_html_prefixes") or ())
    src_uri: str = page.file.src_uri
    if all_prefixes and src_uri.startswith(all_prefixes):
        keep, escape_references = ALL_ESCAPE_KEEP, True
    elif html_prefixes and src_uri.startswith(html_prefixes):
        keep, escape_references = HTML_ELEMENTS, False
    else:
        return markdown
    parts: list[str] = []
    last = 0
    for match in _FENCE.finditer(markdown):
        head = markdown[last : match.start()]
        parts.append(_escape_text(head, keep=keep, escape_references=escape_references))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_escape_text(markdown[last:], keep=keep, escape_references=escape_references))
    return "".join(parts)
