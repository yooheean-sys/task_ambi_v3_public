"""一括 PDF を検査する: ページ数・しおり・埋め込みフォント・指定した文字列の有無・漢字の部首化け。

    uv run --group docs python check_pdf.py [--pdf site/pdf/site.pdf] [--expect 文字列 ...]

- しおりが 0 件なら失敗（exporter はしおりを付けない。hooks/pdf_outline.py が付ける）。
- 康熙部首（U+2F00〜U+2FDF）が本文に出たら失敗。Noto Sans CJK を Chromium が Type3 で埋め込むと、
  「行」「入」などが部首の文字として記録され、PDF 内の検索・
  コピーが壊れる（pdf.css で IPA ゴシックを優先する）。
- `--expect` の文字列が本文に無ければ失敗（空白・改行を無視して探す）。5 種（README の題・
  設計文書の一文・
  CSV のセル・図中の語・docstring の一文・REST API の summary）から 1 つずつ選ぶとよい。
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path


def walk_outline(reader: object, outline: list, depth: int = 0) -> list[tuple[int, str, int]]:
    """しおりを平たく並べる。

    Args:
        reader: `pypdf.PdfReader`。
        outline: しおりの入れ子リスト。
        depth: 深さ。

    Returns:
        `(深さ, 題, ページ番号（1 始まり）)` の一覧。
    """
    out: list[tuple[int, str, int]] = []
    for item in outline:
        if isinstance(item, list):
            out += walk_outline(reader, item, depth + 1)
        else:
            out.append((depth, item.title, reader.get_destination_page_number(item) + 1))  # type: ignore[attr-defined]
    return out


def main() -> int:
    """コマンドラインの入口。

    Returns:
        終了コード（問題があれば 1）。
    """
    from pypdf import PdfReader  # noqa: PLC0415  # mkdocs-exporter の依存

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", default="site/pdf/site.pdf")
    parser.add_argument(
        "--expect", action="append", default=[], help="本文に含まれるべき文字列（繰り返し可）"
    )
    args = parser.parse_args()
    path = Path(args.pdf)
    reader = PdfReader(path)
    pages = len(reader.pages)
    outline = walk_outline(reader, reader.outline)
    print(f"PDF: {path}（{path.stat().st_size / 1e6:.1f} MB）ページ {pages}")
    print("しおり:", len(outline), "最上位:", [(t, p) for d, t, p in outline if d == 0][:12])

    fonts: Counter[str] = Counter()
    step = max(1, pages // 60)
    for i in range(0, pages, step):
        res = reader.pages[i].get("/Resources") or {}
        for font in (res.get("/Font") or {}).values():
            font = font.get_object()
            fonts[f"{font.get('/Subtype')}:{str(font.get('/BaseFont')).split('+')[-1]}"] += 1
    print("フォント（標本）:", fonts.most_common(8))

    text = "".join((reader.pages[i].extract_text() or "") for i in range(pages))
    flat = "".join(text.split())
    radicals = sum(1 for ch in text if 0x2F00 <= ord(ch) <= 0x2FDF)
    print("部首に化けた文字:", radicals)
    problems: list[str] = []
    if not outline:
        problems.append("しおりが無い")
    if radicals:
        problems.append(f"康熙部首が {radicals} 文字ある（日本語フォントを TrueType にする）")
    for needle in args.expect:
        n = flat.count("".join(needle.split()))
        print(f"  「{needle}」: {n}")
        if not n:
            problems.append(f"本文に無い: {needle}")
    print("問題:", len(problems))
    for p in problems:
        print("  ", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
