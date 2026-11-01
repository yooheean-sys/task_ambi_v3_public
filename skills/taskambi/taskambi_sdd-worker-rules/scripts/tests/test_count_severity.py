"""count_severity.py のテスト。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "count_severity.py"

sys.path.insert(0, str(SCRIPT.parent))
from count_severity import count_severity  # noqa: E402


def run_cli(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout


def test_severity_column_by_name_not_position():
    md = (
        "| ID | Severity | Summary |\n"
        "|----|----------|---------|\n"
        "| A1 | CRITICAL | x |\n"
        "| A2 | high | y |\n"
        "| A3 | LOW | z |\n"
    )
    result = count_severity(md)
    assert result == {"critical": 1, "high": 1, "medium": 0, "low": 1, "table_found": True}


def test_severity_column_at_end():
    md = (
        "| Summary | Severity |\n"
        "|---------|----------|\n"
        "| x | MEDIUM |\n"
        "| y | MEDIUM |\n"
    )
    result = count_severity(md)
    assert result["medium"] == 2
    assert result["table_found"] is True


def test_multiple_tables_are_summed():
    md = (
        "| Severity | X |\n|----------|---|\n| CRITICAL | a |\n"
        "\ntext\n\n"
        "| Severity | Y |\n|----------|---|\n| HIGH | b |\n| CRITICAL | c |\n"
    )
    result = count_severity(md)
    assert result["critical"] == 2
    assert result["high"] == 1


def test_no_table_returns_table_found_false():
    result = count_severity("# 見出しだけ\n表なし\n")
    assert result["table_found"] is False
    assert result["critical"] == 0


def test_table_without_severity_column_is_ignored():
    md = "| ID | 重要度 |\n|----|------|\n| A | 高 |\n"
    result = count_severity(md)
    assert result["table_found"] is False


def test_cli_exit_code_2_when_no_table(tmp_path):
    report = tmp_path / "report.md"
    report.write_text("表なし\n", encoding="utf-8")
    code, out = run_cli(report)
    assert code == 2
    assert '"table_found": false' in out


def test_cli_success(tmp_path):
    report = tmp_path / "analyze-1.md"
    report.write_text(
        "| ID | Severity | 内容 |\n|----|----------|------|\n| A1 | HIGH | x |\n",
        encoding="utf-8",
    )
    code, out = run_cli(report)
    assert code == 0
    assert '"high": 1' in out
