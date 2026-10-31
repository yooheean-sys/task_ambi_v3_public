#!/usr/bin/env python3
"""ハーネスの skills.txt を検証する共通処理。外部依存なし。"""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import sys


def load_skill_paths(root: Path) -> list[PurePosixPath]:
    """登録された skills/ 相対パスだけを返す。不備があればコピー前に失敗する。"""
    manifest = root / "skills.txt"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("skills.txt が無いかシンボリックリンクです")
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError("skills.txt を UTF-8 で読み取れません") from exc
    skills_root = root / "skills"
    if skills_root.is_symlink():
        raise ValueError("skills/ にシンボリックリンクは指定できません")
    result: list[PurePosixPath] = []
    seen: set[PurePosixPath] = set()
    for lineno, line in enumerate(lines, 1):
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        path = PurePosixPath(raw)
        if (
            path.is_absolute()
            or str(path) != raw
            or any(part in ("", ".", "..") or part.startswith(".") for part in raw.split("/"))
            or any(char in raw for char in "\\:*?[]#")
            or any(ord(char) < 32 or ord(char) == 127 for char in raw)
        ):
            raise ValueError(f"skills.txt:{lineno}: 不正な相対パスです")
        if path in seen:
            raise ValueError(f"skills.txt:{lineno}: スキルが重複しています")
        current = skills_root
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"skills.txt:{lineno}: シンボリックリンクは指定できません")
        if not current.is_dir() or not (current / "SKILL.md").is_file():
            raise ValueError(f"skills.txt:{lineno}: スキルディレクトリまたは SKILL.md がありません")
        # リンク経由で登録範囲外のファイルが配布されることを防ぐ。
        def walk_error(exc: OSError) -> None:
            raise ValueError(f"skills.txt:{lineno}: スキル内を走査できません") from exc

        for parent, dirs, files in os.walk(current, followlinks=False, onerror=walk_error):
            for name in dirs + files:
                child = Path(parent) / name
                if child.is_symlink() or not (child.is_file() or child.is_dir()):
                    raise ValueError(f"skills.txt:{lineno}: スキル内にリンクまたは通常でないファイルがあります")
        seen.add(path)
        result.append(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="skills.txt を検証して登録パスを列挙する")
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        selected = load_skill_paths(args.root)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for path in selected:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
