"""uv.lock の前後を比べ、追加・削除・版が変わったパッケージを表示する。

docs 依存を足したときに、既存パッケージの版が動いていないこと（稼働中のアプリに影響しない
こと）を確かめる。

    python lock_diff.py                    # git の HEAD の uv.lock と作業ツリーの uv.lock を比べる
    python lock_diff.py --before OLD.lock  # 退避しておいた uv.lock と比べる（未 commit のとき）

既存パッケージの版が 1 つでも変わっていれば終了コード 1。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path


def versions(text: str) -> dict[str, str]:
    """uv.lock の本文からパッケージ名 → 版を取り出す。

    Args:
        text: uv.lock の本文。

    Returns:
        パッケージ名 → 版（ワークスペースのメンバなど版の無いものは空文字）。
    """
    data = tomllib.loads(text)
    return {p["name"]: str(p.get("version", "")) for p in data.get("package", [])}


def main() -> int:
    """コマンドラインの入口。

    Returns:
        終了コード（既存パッケージの版が変わっていれば 1）。
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--before", help="比べる元の uv.lock（省略時は git の HEAD）")
    parser.add_argument("--after", default="uv.lock")
    args = parser.parse_args()
    if args.before:
        before_text = Path(args.before).read_text(encoding="utf-8")
    else:
        result = subprocess.run(
            ["git", "--no-optional-locks", "show", "HEAD:uv.lock"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print("git の HEAD に uv.lock が無い。--before で比べる元を指定する")
            return 2
        before_text = result.stdout
    before = versions(before_text)
    after = versions(Path(args.after).read_text(encoding="utf-8"))
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = {
        k: (before[k], after[k]) for k in before.keys() & after.keys() if before[k] != after[k]
    }
    print(f"追加 {len(added)}: {', '.join(added)}")
    print(f"削除 {len(removed)}: {', '.join(removed)}")
    print(f"版が変わった既存 {len(changed)}: {changed}")
    return 1 if changed or removed else 0


if __name__ == "__main__":
    sys.exit(main())
