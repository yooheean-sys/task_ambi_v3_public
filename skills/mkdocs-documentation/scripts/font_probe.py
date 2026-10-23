"""Chromium の PDF で、フォントごとに日本語が正しく取り出せるか（検索・コピーできるか）を比べる。

PDF 用のフォントを決めるときに使う。Noto Sans CJK（CFF）は Type3 で埋め込まれ、「行」「入」などが
康熙部首の文字として記録される。TrueType の日本語フォント（IPA ゴシックなど）は Type0 で、
正しく取り出せる。

    uv run --group docs python font_probe.py [--font "IPAGothic" --font "Noto Sans CJK JP" ...]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

SAMPLE = "SettingsReader の実行・入力・盤面・単一 — get_project(project_key) を呼ぶ"
DEFAULT_FONTS = (
    '"IPAGothic"',
    '"IPAexGothic"',
    '"Noto Sans CJK JP"',
    '"Liberation Sans", "IPAGothic"',
)


async def probe(fonts: list[str], sample: str) -> None:
    """各フォントで PDF を作り、取り出した文字列と埋め込み形式を表示する。

    Args:
        fonts: CSS の font-family の値。
        sample: 試す文字列。
    """
    from playwright.async_api import async_playwright  # noqa: PLC0415
    from pypdf import PdfReader  # noqa: PLC0415

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        with tempfile.TemporaryDirectory() as tmp:
            for i, font in enumerate(fonts):
                page = await browser.new_page()
                await page.set_content(
                    f"<html lang='ja'><body style='font-family: {font}'>{sample}</body></html>"
                )
                out = Path(tmp, f"probe{i}.pdf")
                await page.pdf(path=str(out))
                await page.close()
                reader = PdfReader(out)
                got = (reader.pages[0].extract_text() or "").strip()
                kinds = {
                    f"{f.get_object().get('/Subtype')}:{str(f.get_object().get('/BaseFont')).split('+')[-1]}"
                    for f in reader.pages[0]["/Resources"]["/Font"].values()
                }
                radicals = sum(1 for ch in got if 0x2F00 <= ord(ch) <= 0x2FDF)
                same = "".join(got.split()) == "".join(sample.split())
                wanted = {name.strip().strip('"').replace(" ", "") for name in font.split(",")}
                embedded = " ".join(kinds).replace(" ", "")
                if any(k.startswith("/Type3") for k in kinds):
                    note = "（Type3 で埋め込み。フォント名が残らず、文字の対応も崩れやすい）"
                elif any(w in embedded for w in wanted):
                    note = ""
                else:
                    note = "（未導入: 既定のフォントに落ちた）"
                print(f"{font:34} 一致={same!s:5} 部首={radicals} {sorted(kinds)}{note}\n    {got}")
        await browser.close()


def main() -> int:
    """コマンドラインの入口。

    Returns:
        終了コード（常に 0）。
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--font", action="append", default=[], help='CSS の font-family（例: "IPAGothic"）'
    )
    parser.add_argument("--sample", default=SAMPLE)
    args = parser.parse_args()
    asyncio.run(probe(args.font or list(DEFAULT_FONTS), args.sample))
    return 0


if __name__ == "__main__":
    sys.exit(main())
