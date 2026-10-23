"""count_convergence_rounds.py のテスト。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "count_convergence_rounds.py"

sys.path.insert(0, str(SCRIPT.parent))
from count_convergence_rounds import count_convergence  # noqa: E402


def run_cli(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout


def test_zero_when_no_convergence():
    assert count_convergence("## Phase 1: Setup\n## Phase 2: Implement\n") == 0


def test_counts_convergence_headings():
    text = (
        "## Phase 1: Setup\n"
        "## Phase 2: Convergence\n"
        "task\n"
        "## Phase 3: Convergence\n"
    )
    assert count_convergence(text) == 2


def test_ignores_similar_headings():
    text = (
        "## Phase 2: Convergence 前の確認\n"  # これは数える(Convergence で始まる)
        "## Phase 3:Implementation\n"        # コロンなし → 数えない
        "### Phase 4: Convergence\n"         # h3 → 数えない
        "## Phase X: Convergence\n"          # 数字でない → 数えない
    )
    assert count_convergence(text) == 1


def test_allows_trailing_text_and_spaces():
    assert count_convergence("##  Phase 12:  Convergence (retry)\n") == 1


def test_cli(tmp_path):
    tasks = tmp_path / "tasks.md"
    tasks.write_text("## Phase 1: A\n## Phase 2: Convergence\n", encoding="utf-8")
    code, out = run_cli(tasks)
    assert code == 0
    assert '"convergence_phases": 1' in out
