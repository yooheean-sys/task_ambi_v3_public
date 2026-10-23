#!/usr/bin/env python3
"""count_convergence_rounds.py — tasks.md の Convergence フェーズ数を数える。

speckit-converge が追記する `## Phase <数字>: Convergence` 形式の見出しを数える。

使い方:
  uv run python <このスクリプトの絶対パス> <tasks.md>

出力は JSON: {"convergence_phases": n}
Python 3.11 以上・標準ライブラリのみ。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PATTERN = re.compile(r"^##\s+Phase\s+\d+:\s+Convergence\b")


def count_convergence(text: str) -> int:
    return sum(1 for line in text.splitlines() if PATTERN.match(line))


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: count_convergence_rounds.py <tasks.md>"}, ensure_ascii=False))
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(json.dumps({"error": f"file not found: {path}"}, ensure_ascii=False))
        return 2
    result = {"convergence_phases": count_convergence(path.read_text(encoding="utf-8"))}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
