#!/usr/bin/env python3
"""guard_check.py — SDD パイプラインのガード。

RED_PATHS(変更されたら即停止)と YELLOW_PATHS(追加のみ可)の違反を検知する。

判定は2方式:
  A) git が追跡している変更: `git status --porcelain -z`(未追跡を含む)と
     `git diff HEAD --numstat -z` を使い、HEAD との差分で判定する。
  B) gitignore されて git から見えない RED パス: 内容ハッシュのベースライン
     (既定: <root>/.hermes/sdd-guard-baseline.json)と比較する。
     ベースラインの作成・更新は人間の操作(--init-baseline)。

使い方(カードの作業場所 = リポジトリルートで実行):
  uv run python <このスクリプトの絶対パス>            # 判定。違反があれば終了コード 1
  uv run python <このスクリプトの絶対パス> --init-baseline   # ベースライン作成(人間専用)

出力は JSON: {"ok": bool, "violations": [{"path", "rule", "change"}, ...]}
Python 3.11 以上・標準ライブラリのみ。
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BASELINE = ".hermes/sdd-guard-baseline.json"
CONFIG_PATH = ".hermes/sdd-guard.toml"


# ---------------------------------------------------------------- ユーティリティ

def is_forbidden_path(path: str) -> bool:
    """作業場所が /mnt/ 配下(Windows 側)なら True。"""
    p = path.replace("\\", "/")
    return p == "/mnt" or p.startswith("/mnt/")


def glob_match(path: str, pattern: str) -> bool:
    """`**` を正しく扱う glob 一致(path はリポジトリ相対・/ 区切り)。

    - `**/` は 0 個以上のディレクトリ階層に一致
    - 末尾 `/**` はその配下すべてに一致
    - それ以外は fnmatch(1 セグメント内の * ? [..])
    """
    path = path.lstrip("/")
    pattern = pattern.lstrip("/")
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/") or fnmatch.fnmatch(path, prefix + "/**")
    if "**" in pattern:
        # `a/**/b` 形: セグメント分割して再帰的に比較
        return _double_star_match(path.split("/"), pattern.split("/"))
    return fnmatch.fnmatch(path, pattern)


def _double_star_match(path_parts: list[str], pat_parts: list[str]) -> bool:
    if not pat_parts:
        return not path_parts
    head, rest = pat_parts[0], pat_parts[1:]
    if head == "**":
        # ** が 0..n セグメントに一致
        for i in range(len(path_parts) + 1):
            if _double_star_match(path_parts[i:], rest):
                return True
        return False
    if not path_parts:
        return False
    return fnmatch.fnmatchcase(path_parts[0], head) and _double_star_match(path_parts[1:], rest)


def match_any(path: str, patterns: list[str]) -> str | None:
    for pat in patterns:
        if glob_match(path, pat):
            return pat
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- git 操作

def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=False,
    ).stdout.decode("utf-8", errors="surrogateescape")


def git_z(root: Path, *args: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True,
    ).stdout
    return [e.decode("utf-8", errors="surrogateescape") for e in out.split(b"\0") if e]


def repo_root(cwd: Path) -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()
    return Path(out)


def collect_git_changes(root: Path) -> list[dict]:
    """git に見える変更(未追跡を含む・ignored は含まない)を列挙する。"""
    entries = git_z(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    changes: list[dict] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            orig = entries[i + 1] if i + 1 < len(entries) else ""
            changes.append({"path": path, "change": "renamed", "orig": orig})
            i += 2
            continue
        if xy == "??":
            changes.append({"path": path, "change": "added"})
        elif "D" in xy:
            changes.append({"path": path, "change": "deleted"})
        elif "A" in xy:
            changes.append({"path": path, "change": "added"})
        else:
            changes.append({"path": path, "change": "modified"})
        i += 1
    return changes


def numstat_deletions(root: Path) -> dict[str, int]:
    """HEAD 比較の削除行数を path -> deleted_lines で返す(未追跡ファイルは出ない)。"""
    entries = git_z(root, "diff", "HEAD", "--numstat", "-z")
    result: dict[str, int] = {}
    i = 0
    while i < len(entries):
        parts = entries[i].split("\t")
        if len(parts) == 3 and parts[2] == "":
            # リネーム: 次の2要素が old/new
            if i + 2 < len(entries):
                result[entries[i + 2]] = int(parts[1]) if parts[1].isdigit() else 0
            i += 3
            continue
        if len(parts) == 3:
            result[parts[2]] = int(parts[1]) if parts[1].isdigit() else 0
        i += 1
    return result


def ignored_red_files(root: Path, red_patterns: list[str], excludes: list[str]) -> list[str]:
    """gitignore されて git に見えない未追跡ファイルのうち RED 一致を列挙する。"""
    ignored = git_z(root, "ls-files", "-o", "-i", "--exclude-standard", "-z")
    out = []
    for path in ignored:
        if match_any(path, excludes):
            continue
        if match_any(path, red_patterns):
            out.append(path)
    return sorted(out)


# ---------------------------------------------------------------- メイン判定

def load_config(root: Path) -> dict:
    cfg_path = root / CONFIG_PATH
    if not cfg_path.is_file():
        print(json.dumps({
            "ok": False,
            "violations": [{"path": CONFIG_PATH, "rule": "config-missing",
                            "change": "ガード設定ファイルが見つからない"}],
        }, ensure_ascii=False, indent=2))
        sys.exit(2)
    with cfg_path.open("rb") as f:
        cfg = tomllib.load(f)
    return {
        "red": list(cfg.get("red_paths", [])),
        "yellow": list(cfg.get("yellow_paths", [])),
        "red_exclude": list(cfg.get("red_exclude", [])),
        "baseline_file": cfg.get("baseline_file", DEFAULT_BASELINE),
    }


def run_check(root: Path) -> int:
    violations: list[dict] = []

    # 0. 作業場所が /mnt/ 配下なら即違反
    if is_forbidden_path(str(root)):
        violations.append({"path": str(root), "rule": "workspace-mnt",
                           "change": "作業場所が /mnt/ 配下(Windows 側)になっている"})
        print(json.dumps({"ok": False, "violations": violations}, ensure_ascii=False, indent=2))
        return 1

    cfg = load_config(root)
    red, yellow = cfg["red"], cfg["yellow"]
    red_exclude = cfg["red_exclude"]
    baseline_rel = cfg["baseline_file"]

    # A) git に見える変更の判定
    changes = collect_git_changes(root)
    dels = numstat_deletions(root)
    for c in changes:
        path, change = c["path"], c["change"]
        if path == baseline_rel:
            continue  # ベースライン自身は対象外(人間が更新する)
        if match_any(path, red_exclude):
            continue
        pat = match_any(path, red)
        if pat:
            violations.append({"path": path, "rule": "red", "change": change})
            if change == "renamed" and c.get("orig"):
                violations.append({"path": c["orig"], "rule": "red", "change": "rename 元"})
            continue
        pat = match_any(path, yellow)
        if pat:
            if change in ("deleted", "renamed"):
                violations.append({"path": path, "rule": "yellow", "change": change})
            elif change == "modified" and dels.get(path, 0) > 0:
                violations.append({"path": path, "rule": "yellow",
                                   "change": f"既存行の削除を含む変更(削除 {dels[path]} 行)"})

    # B) gitignore された RED パスはハッシュベースラインと比較
    ignored = ignored_red_files(root, red, red_exclude)
    baseline_path = root / baseline_rel
    if ignored:
        if not baseline_path.is_file():
            violations.append({"path": baseline_rel, "rule": "baseline-missing",
                               "change": "gitignore された RED パスがあるのにベースラインがない。"
                                         "人間に --init-baseline の実行を依頼すること"})
        else:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            base_files: dict[str, str] = baseline.get("files", {})
            current = {p: sha256_file(root / p) for p in ignored if (root / p).is_file()}
            for p, h in current.items():
                if p not in base_files:
                    violations.append({"path": p, "rule": "red-baseline", "change": "not-in-baseline(新規)"})
                elif base_files[p] != h:
                    violations.append({"path": p, "rule": "red-baseline", "change": "hash-mismatch(変更)"})
            for p in base_files:
                if p not in current:
                    violations.append({"path": p, "rule": "red-baseline", "change": "missing(削除)"})

    print(json.dumps({"ok": not violations, "violations": violations}, ensure_ascii=False, indent=2))
    return 0 if not violations else 1


def init_baseline(root: Path) -> int:
    """ベースラインを作成・更新する。人間の操作。ワーカーからは実行しない。"""
    cfg = load_config(root)
    ignored = ignored_red_files(root, cfg["red"], cfg["red_exclude"])
    files = {}
    for p in ignored:
        fp = root / p
        if fp.is_file():
            files[p] = sha256_file(fp)
    baseline = {
        "version": 1,
        "root": str(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    out = root / cfg["baseline_file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "baseline": str(out), "files": len(files)},
                     ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="SDD ガード(RED/YELLOW パス違反の検知)")
    ap.add_argument("--root", help="リポジトリルート(既定: cwd から git rev-parse で解決)")
    ap.add_argument("--init-baseline", action="store_true",
                    help="gitignore された RED パスのハッシュベースラインを作成・更新(人間専用)")
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root(Path.cwd())
    if args.init_baseline:
        return init_baseline(root)
    return run_check(root)


if __name__ == "__main__":
    sys.exit(main())
