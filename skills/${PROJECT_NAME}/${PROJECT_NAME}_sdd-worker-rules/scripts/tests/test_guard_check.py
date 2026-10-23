"""guard_check.py のテスト。

一時ディレクトリに git リポジトリを作って検証する(プロジェクトの実ファイルでは試さない)。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "guard_check.py"

sys.path.insert(0, str(SCRIPT.parent))
from guard_check import glob_match, is_forbidden_path  # noqa: E402

CONFIG = "sdd-guard.toml"
CFG_DIR = ".hermes"

RED_YELLOW = {
    "red_paths": ["design/**", ".specify/**"],
    "yellow_paths": ["common/interfaces/**"],
    "red_exclude": [".specify/feature.json"],
}


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "test")
    (root / CFG_DIR).mkdir()
    (root / CFG_DIR / CONFIG).write_text(
        'red_paths = ["design/**", ".specify/**"]\n'
        'yellow_paths = ["common/interfaces/**"]\n'
        'red_exclude = [".specify/feature.json"]\n',
        encoding="utf-8",
    )
    (root / "design").mkdir()
    (root / "design" / "base.md").write_text("# 基本設計\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (root / "common").mkdir()
    (root / "common" / "interfaces").mkdir()
    (root / "common" / "interfaces" / "api.py").write_text("X = 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def run_guard(root: Path, *extra: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *extra],
        capture_output=True, text=True,
    )
    assert proc.stdout, proc.stderr
    return proc.returncode, json.loads(proc.stdout)


# ---------------------------------------------------------------- 基本系

def test_clean_repo_is_ok(repo: Path):
    code, out = run_guard(repo)
    assert code == 0
    assert out["ok"] is True
    assert out["violations"] == []


def test_green_change_is_ok(repo: Path):
    (repo / "src" / "main.py").write_text("print('changed')\n", encoding="utf-8")
    code, _ = run_guard(repo)
    assert code == 0


def test_red_modify_is_violation(repo: Path):
    (repo / "design" / "base.md").write_text("# 改ざん\n", encoding="utf-8")
    code, out = run_guard(repo)
    assert code == 1
    assert any(v["rule"] == "red" and v["path"] == "design/base.md" for v in out["violations"])


def test_red_untracked_add_is_violation(repo: Path):
    (repo / "design" / "new.md").write_text("new\n", encoding="utf-8")
    code, out = run_guard(repo)
    assert code == 1
    assert any(v["rule"] == "red" and v["change"] == "added" for v in out["violations"])


def test_red_exclude_is_allowed(repo: Path):
    (repo / ".specify").mkdir()
    (repo / ".specify" / "feature.json").write_text('{"feature_directory": "specs/001-x"}\n', encoding="utf-8")
    code, _ = run_guard(repo)
    assert code == 0


def test_red_delete_is_violation(repo: Path):
    (repo / "design" / "base.md").unlink()
    code, out = run_guard(repo)
    assert code == 1
    assert any(v["rule"] == "red" and v["change"] == "deleted" for v in out["violations"])


# ---------------------------------------------------------------- YELLOW

def test_yellow_new_file_is_ok(repo: Path):
    (repo / "common" / "interfaces" / "new.py").write_text("Y = 2\n", encoding="utf-8")
    code, _ = run_guard(repo)
    assert code == 0


def test_yellow_line_addition_is_ok(repo: Path):
    (repo / "common" / "interfaces" / "api.py").write_text("X = 1\nY = 2\n", encoding="utf-8")
    code, _ = run_guard(repo)
    assert code == 0


def test_yellow_line_deletion_is_violation(repo: Path):
    (repo / "common" / "interfaces" / "api.py").write_text("# empty\n", encoding="utf-8")
    code, out = run_guard(repo)
    assert code == 1
    assert any(v["rule"] == "yellow" and "削除" in v["change"] for v in out["violations"])


def test_yellow_delete_file_is_violation(repo: Path):
    (repo / "common" / "interfaces" / "api.py").unlink()
    code, out = run_guard(repo)
    assert code == 1
    assert any(v["rule"] == "yellow" and v["change"] == "deleted" for v in out["violations"])


# ---------------------------------------------------------------- ベースライン(gitignore された RED)

def test_baseline_detects_ignored_red_change(repo: Path):
    (repo / ".gitignore").write_text("secret/\n", encoding="utf-8")
    (repo / CFG_DIR / CONFIG).write_text(
        'red_paths = ["design/**", "secret/**"]\nyellow_paths = []\n',
        encoding="utf-8",
    )
    (repo / "secret").mkdir()
    (repo / "secret" / "constitution.md").write_text("v1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add gitignore")

    # ベースライン未作成 → baseline-missing 違反
    code, out = run_guard(repo)
    assert code == 1
    assert any(v["rule"] == "baseline-missing" for v in out["violations"])

    # ベースライン作成後は OK
    code, _ = run_guard(repo, "--init-baseline")
    assert code == 0
    code, out = run_guard(repo)
    assert code == 0, out

    # 内容変更を検知
    (repo / "secret" / "constitution.md").write_text("v2\n", encoding="utf-8")
    code, out = run_guard(repo)
    assert code == 1
    assert any(v["rule"] == "red-baseline" and "変更" in v["change"] for v in out["violations"])

    # 新規追加を検知
    run_guard(repo, "--init-baseline")
    (repo / "secret" / "added.md").write_text("new\n", encoding="utf-8")
    code, out = run_guard(repo)
    assert code == 1
    assert any(v["rule"] == "red-baseline" and "新規" in v["change"] for v in out["violations"])

    # 削除を検知
    run_guard(repo, "--init-baseline")
    (repo / "secret" / "added.md").unlink()
    code, out = run_guard(repo)
    assert code == 1
    assert any(v["rule"] == "red-baseline" and "削除" in v["change"] for v in out["violations"])


# ---------------------------------------------------------------- パス判定

def test_mnt_path_is_forbidden():
    assert is_forbidden_path("/mnt/c/Users/x") is True
    assert is_forbidden_path("/mnt") is True
    assert is_forbidden_path("${USER_HOME}/repo") is False


def test_glob_match_double_star():
    assert glob_match("docs/design/phase1/x.md", "docs/design/**")
    assert glob_match("docs/design", "docs/design/**") is True  # ディレクトリ自体も保護対象に含める(安全側)
    assert glob_match("pyproject.toml", "pyproject.toml")
    assert glob_match("a/b/c.py", "a/**/*.py")
    assert glob_match("a/c.py", "a/**/*.py")
    assert glob_match(".specify/feature.json", ".specify/**")


def test_missing_config_is_error(tmp_path: Path):
    root = tmp_path / "noconfig"
    root.mkdir()
    git(root, "init", "-q")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "config-missing" in proc.stdout
