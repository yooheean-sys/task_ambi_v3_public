"""全ての図（.mmd）のページを Chromium で開き、mermaid の描画エラーを拾う。

Material は図を外から覗けない shadow DOM に描くので、DOM ではなくコンソールのエラーと、描画後の
図の高さ（構文エラーだと小さな枠になる）で判定する。HTML ビルド（ENABLE_PDF_EXPORT なし）
の site/ に対して使う。
site/ を一時ポートで配信するので、別にサーバを立てなくてよい。
Material は mermaid を CDN から読むので
ネットワークが要る。

    uv run --group docs python check_mermaid.py [--site site]
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docstring_audit import load_mkdocs_config  # noqa: E402


def serve(site: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    """site/ を 127.0.0.1 の空きポートで配信する（デーモンスレッド）。

    Args:
        site: 出力フォルダ。

    Returns:
        サーバとポート。
    """

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002  # 基底の引数名
            return

    handler = functools.partial(QuietHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


async def check(pages: list[str], port: int) -> list[tuple[str, float, list[str]]]:
    """各ページを開いて、エラーと図の高さを調べる。

    Args:
        pages: site/ 相対のページ（末尾 `/`）。
        port: 配信ポート。

    Returns:
        問題のあったページの `(ページ, 高さ, エラー)`。
    """
    from playwright.async_api import async_playwright  # noqa: PLC0415

    bad: list[tuple[str, float, list[str]]] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for rel in pages:
            page = await browser.new_page()
            errors: list[str] = []
            page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
            await page.goto(f"http://127.0.0.1:{port}/{rel}", wait_until="networkidle")
            await page.wait_for_timeout(1500)
            height = await page.evaluate(
                "Math.max(0, ...[...document.querySelectorAll('div.mermaid')]"
                ".map(e => e.getBoundingClientRect().height))"
            )
            if errors or height < 40:
                bad.append((rel, height, errors[:2]))
            await page.close()
        await browser.close()
    return bad


def main() -> int:
    """コマンドラインの入口。

    Returns:
        終了コード（問題があれば 1）。
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--site", default="site")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    config = load_mkdocs_config(root / "mkdocs.yml")
    docs = root / (config.get("docs_dir") or "docs")
    design_rel = (
        (((config.get("extra") or {}).get("docs_build")) or {}).get("design_dir") or ""
    ).strip("/")
    if not design_rel:
        print("設計文書の置き場（extra.docs_build.design_dir）が無いので図は無い")
        return 0
    pages = sorted(
        f"{p.relative_to(docs).with_suffix('').as_posix()}/"
        for p in (docs / design_rel).rglob("*.mmd")
    )
    server, port = serve(root / args.site)
    try:
        bad = asyncio.run(check(pages, port))
    finally:
        server.shutdown()
    print("図:", len(pages), "問題:", len(bad))
    for item in bad:
        print("  ", item)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
