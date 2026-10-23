#!/usr/bin/env python3
"""count_severity.py — Markdown レポートの Severity 件数を集計する。

ヘッダ行に "Severity" 列を持つ表を探し、その列の CRITICAL / HIGH / MEDIUM / LOW
を数える。analyze と converge の両方の表に対応させるため、列の位置ではなく
列名で判定する。複数の表があれば合算する。

使い方:
  uv run python <このスクリプトの絶対パス> <レポート.md>

出力は JSON: {"critical": n, "high": n, "medium": n, "low": n, "table_found": bool}
表が1つも見つからなければ table_found=false で終了コード 2。
Python 3.11 以上・標準ライブラリのみ。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def split_row(line: str) -> list[str]:
    """`| a | b |` 形式の行をセル列に分割する。"""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [cell.strip() for cell in text.split("|")]


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells)


def count_severity(markdown: str) -> dict:
    counts = {s.lower(): 0 for s in SEVERITIES}
    table_found = False
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip().startswith("|"):
            i += 1
            continue
        header = split_row(line)
        severity_idx = next(
            (idx for idx, cell in enumerate(header) if cell.strip().lower() == "severity"),
            None,
        )
        if severity_idx is None:
            i += 1
            continue
        # 次行は区切り行のはず
        if i + 1 >= len(lines) or not is_separator_row(split_row(lines[i + 1])):
            i += 1
            continue
        table_found = True
        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            cells = split_row(lines[j])
            if severity_idx < len(cells):
                value = cells[severity_idx].strip().upper()
                if value in SEVERITIES:
                    counts[value.lower()] += 1
            j += 1
        i = j
    return {**counts, "table_found": table_found}


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: count_severity.py <report.md>"}, ensure_ascii=False))
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(json.dumps({"error": f"file not found: {path}"}, ensure_ascii=False))
        return 2
    result = count_severity(path.read_text(encoding="utf-8"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["table_found"] else 2


if __name__ == "__main__":
    sys.exit(main())
