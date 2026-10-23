"""生成サイト（site/）に README・設計文書・API リファレンス・REST API が載っているかを数える。

リポジトリルートで、`mkdocs build` の後に呼ぶ。設定（設計フォルダ・OpenAPI のダンプ先）
は mkdocs.yml の
`extra.docs_build` から読む。問題が 1 件でもあれば終了コード 1。

    python verify_site.py [--site site]

検査すること:
- 設計文書: md・mmd・csv がそれぞれページになっているか。
  図は mermaid ブロック（PDF ビルドなら SVG 画像）、
  表は見出しの列数・行数・各行の列数が元の CSV と一致するか。
  本文の `<占位子>` が表示されるか（消えていないか）。
- API リファレンス: 各ページに mkdocstrings の描画があるか。
- REST API: 全操作の summary が表示されるか。
  h1 がページ題と info.title の 2 個だけか（docstring の行頭 # が見出しになっていないか）。
- ホーム: README の題が載っているか。
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docstring_audit import load_mkdocs_config  # noqa: E402

PLACEHOLDER = re.compile(r"<[A-Za-z_][A-Za-z0-9_]*>")


def page_path(site: Path, rel_md: Path) -> Path:
    """`x/y.md` → `site/x/y/index.html`（use_directory_urls の既定）。

    Args:
        site: 出力フォルダ。
        rel_md: docs/ 相対の md パス。

    Returns:
        HTML のパス。
    """
    if rel_md.name == "index.md":
        return site / rel_md.parent / "index.html"
    return site / rel_md.with_suffix("") / "index.html"


def text_of(path: Path) -> str:
    """HTML の表示文字列（タグを除いてからエスケープを戻す）。

    Args:
        path: HTML のパス。

    Returns:
        表示される文字列のおおよそ。
    """
    return html.unescape(re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8")))


def check_design(site: Path, design: Path, docs: Path, problems: list[str]) -> dict[str, int]:
    """設計文書のページを検査する。

    Args:
        site: 出力フォルダ。
        design: 設計文書の置き場。
        docs: docs/ フォルダ。
        problems: 見つけた問題を積む先。

    Returns:
        種類ごとのページ数。
    """
    counts = {"md": 0, "mmd": 0, "csv": 0}
    for src in sorted(design.rglob("*")):
        if src.suffix not in (".md", ".mmd", ".csv") or src.name == "SUMMARY.md":
            continue
        out = page_path(site, src.relative_to(docs).with_suffix(".md"))
        if not out.is_file():
            problems.append(f"ページが無い: {src}")
            continue
        counts[src.suffix[1:]] += 1
        raw = out.read_text(encoding="utf-8")
        shown = text_of(out)
        body = src.read_text(encoding="utf-8-sig")
        if (
            src.suffix == ".mmd"
            and 'class="mermaid"' not in raw
            and not re.search(r"<img[^>]+\.svg", raw)
        ):
            problems.append(f"図が描かれていない（mermaid も SVG も無い）: {src}")
        if src.suffix == ".csv":
            rows = list(csv.reader(io.StringIO(body)))
            table = re.search(r"<table>.*?</table>", raw, re.S)
            if not table or not rows:
                problems.append(f"表が無い: {src}")
                continue
            head = re.search(r"<thead>.*?</thead>", table.group(0), re.S)
            tbody = re.search(r"<tbody>.*?</tbody>", table.group(0), re.S)
            head_cols = len(re.findall(r"<th[ >]", head.group(0))) if head else 0
            body_rows = re.findall(r"<tr>(.*?)</tr>", tbody.group(0), re.S) if tbody else []
            bad = [
                i for i, r in enumerate(body_rows) if len(re.findall(r"<td[ >]", r)) != len(rows[0])
            ]
            if head_cols != len(rows[0]) or len(body_rows) != len(rows) - 1 or bad:
                shape = f"見出し {head_cols}/{len(rows[0])} 行 {len(body_rows)}/{len(rows) - 1}"
                problems.append(f"表の形が違う: {src} {shape} 列違いの行 {bad[:3]}")
            cells = [c for r in rows for c in r]
        else:
            cells = [re.sub(r"```.*?```", "", body, flags=re.S)] if src.suffix == ".md" else []
        for cell in cells:
            for ph in set(PLACEHOLDER.findall(re.sub(r"`[^`]*`", "", cell))):
                if ph.strip("<>/").lower() == "br":
                    continue
                if ph not in shown:
                    problems.append(f"占位子が表示されない: {src} {ph}")
    return counts


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
    site = root / args.site
    config = load_mkdocs_config(root / "mkdocs.yml")
    docs = root / (config.get("docs_dir") or "docs")
    settings = ((config.get("extra") or {}).get("docs_build")) or {}
    problems: list[str] = []

    design_rel = (settings.get("design_dir") or "").strip("/")
    if design_rel and (docs / design_rel).is_dir():
        print("設計文書のページ:", check_design(site, docs / design_rel, docs, problems))

    api_pages = [p for p in (site / "api").rglob("index.html") if "SUMMARY" not in p.parts]
    no_doc = [p for p in api_pages if 'class="doc doc-' not in p.read_text(encoding="utf-8")]
    print("API リファレンスのページ:", len(api_pages), "／描画の無いページ:", len(no_doc))
    problems += [f"API リファレンスに描画が無い: {p.relative_to(site)}" for p in no_doc]
    if (site / "api" / "SUMMARY").exists():
        problems.append(
            "ナビ定義 SUMMARY.md がページとして出力されている（hooks/exclude_nav_files.py を確認）"
        )

    openapi_json = root / (settings.get("openapi_output") or "docs/openapi/openapi.json")
    oad = site / "openapi" / "index.html"
    if settings.get("openapi_app") and oad.is_file() and openapi_json.is_file():
        spec = json.loads(openapi_json.read_text(encoding="utf-8"))
        ops = [
            op for item in spec["paths"].values() for m, op in item.items() if isinstance(op, dict)
        ]
        flat = re.sub(r"\s+", "", text_of(oad))
        missing = [
            op.get("operationId")
            for op in ops
            if op.get("summary") and re.sub(r"\s+", "", op["summary"]) not in flat
        ]
        h1 = oad.read_text(encoding="utf-8").count("<h1")
        print("REST API: 操作", len(ops), "／summary 未表示", missing, "／h1", h1)
        if missing:
            problems.append(f"REST API の summary が表示されない: {missing}")
        if h1 > 2:
            problems.append(
                f"REST API ページの h1 が {h1} 個（docstring の行頭 # が見出しになっていないか）"
            )

    readme = root / "README.md"
    if readme.is_file():
        title = readme.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
        ok = title in text_of(site / "index.html")
        print("ホームに README の題:", ok)
        if not ok:
            problems.append("ホームに README が取り込まれていない")

    print("問題:", len(problems))
    for p in problems[:60]:
        print("  ", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
