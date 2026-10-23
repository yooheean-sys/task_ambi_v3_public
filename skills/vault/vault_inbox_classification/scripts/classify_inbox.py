#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""${VAULT_NAME} vault: 00_inbox のファイルを map.json に従って移動し、分類ログを書き出す。

Usage:
    python3 classify_inbox.py --vault /path/to/vault --map map.json           # dry-run
    python3 classify_inbox.py --vault /path/to/vault --map map.json --apply   # 実行

map.json: [{"file": "...md", "dest": "30_knowledges/ai", "note": "...", "rename": "...md"}]
- file  : 00_inbox 直下のファイル名（必須）
- dest  : vault 相対の移動先ディレクトリ（必須・既存であること。00_inbox 配下は不可）
- note  : 分類ログに書く 1 行メモ（任意）
- rename: 移動時の新しいファイル名（任意・90_keep 番号付けなど）

分類ログは 1 実行につき 1 ファイルとして 00_inbox/logs/ に新規作成する:
    00_inbox/logs/分類ログ_YYYY-MM-DD_HHMM.md
00_inbox/logs 配下のファイルは分類対象外であり、移動先にも指定できない。
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone

INBOX = "00_inbox"
LOGS_DIR = "00_inbox/logs"
LOG_PREFIX = "分類ログ_"
LEGACY_LOG_NAME = "00_分類ログ.md"  # 旧形式（00_inbox 直下に置かれていた累積ログ）
PROTECTED_TOP = (".obsidian", "legacy", "templates", "scripts")
TEMP_DIR = "91_extra/temp"
JST = timezone(timedelta(hours=9))


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def unique_target(path: str) -> str:
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem} {n}{ext}"):
        n += 1
    return f"{stem} {n}{ext}"


def unique_log_path(logs_dir: str, stamp: str) -> str:
    """同一スタンプのログが既にあれば _2, _3 と連番を振る。"""
    log_file = os.path.join(logs_dir, f"{LOG_PREFIX}{stamp}.md")
    n = 2
    while os.path.exists(log_file):
        log_file = os.path.join(logs_dir, f"{LOG_PREFIX}{stamp}_{n}.md")
        n += 1
    return log_file


def main() -> int:
    ap = argparse.ArgumentParser(description="00_inbox classifier mover for ${VAULT_NAME}")
    ap.add_argument("--vault", required=True)
    ap.add_argument("--map", required=True, help="map.json path")
    ap.add_argument(
        "--apply", action="store_true", help="実際に移動・ログ作成する（無ければ dry-run）"
    )
    args = ap.parse_args()

    vault = os.path.abspath(args.vault)
    inbox = os.path.join(vault, INBOX)
    logs_dir = os.path.join(vault, LOGS_DIR)
    if not os.path.isdir(inbox):
        print(f"ERROR: inbox が無い: {inbox}")
        return 1
    try:
        with open(args.map, encoding="utf-8") as f:
            mapping = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: map.json を読めない: {e}")
        return 1
    if not isinstance(mapping, list):
        print("ERROR: map.json は配列であること")
        return 1

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    plan, errors = [], []

    for ent in mapping:
        if not isinstance(ent, dict):
            errors.append("SKIP: map 要素がオブジェクトでない")
            continue
        name = str(ent.get("file", "")).strip()
        dest = str(ent.get("dest", "")).strip().strip("/")
        note = str(ent.get("note", "")).strip()
        rename = str(ent.get("rename", "")).strip()

        if not name or os.path.basename(name) != name:
            errors.append(f"SKIP: file が不正（{name!r}）")
            continue
        # 分類ログ（旧形式・日付付きとも）は対象外。logs 配下のファイルは本来
        # map に入らないが、inbox 直下に紛れた場合も移動させない
        if name == LEGACY_LOG_NAME or name.startswith(LOG_PREFIX):
            errors.append(f"SKIP: 分類ログは対象外（{name}）")
            continue
        src = os.path.join(inbox, name)
        if not os.path.isfile(src):
            errors.append(f"SKIP: 00_inbox に無い（{name}）")
            continue
        if not dest or dest == ".":
            errors.append(f"SKIP: dest が不正（{name} → {dest!r}）")
            continue
        # 00_inbox 配下（logs を含む）への移動は禁止。
        # 「00_inbox/logs のファイルはどこへも分類しない」という要件の担保でもある
        if dest == INBOX or dest.startswith(INBOX + "/"):
            errors.append(f"SKIP: 00_inbox 配下は移動先にできない（{name} → {dest}）")
            continue
        if dest.startswith("..") or dest.split("/")[0] in PROTECTED_TOP:
            errors.append(f"SKIP: 保護領域への移動（{name} → {dest}）")
            continue
        dest_dir = os.path.join(vault, dest)
        if not os.path.isdir(dest_dir):
            errors.append(f"WARN: dest 未存在（{name} → {dest}）")
            continue

        final = os.path.basename(rename) if rename else name
        if not final or final in (".", ".."):
            errors.append(f"SKIP: rename が不正（{name} → {rename!r}）")
            continue

        target = os.path.join(dest_dir, final)
        kind = "MOVE"
        if os.path.exists(target):
            if sha256(src) == sha256(target):
                kind = "DUP"
                dest = TEMP_DIR
                dest_dir = os.path.join(vault, dest)
                target = unique_target(os.path.join(dest_dir, final))
                final = os.path.basename(target)
                note = (note + "；" if note else "") + "移動先に同名同内容あり → temp 退避"
            else:
                kind = "RENAME"
                stem, ext = os.path.splitext(final)
                cand = os.path.join(
                    dest_dir, f"{stem} {datetime.now(JST).strftime('%Y%m%d')}{ext}"
                )
                target = unique_target(cand)
                final = os.path.basename(target)
                note = (note + "；" if note else "") + "移動先に同名別内容あり → 改名して併存"
        plan.append(
            {"kind": kind, "src": src, "dest": dest, "final": final, "note": note, "name": name}
        )

    moved = [p for p in plan if p["kind"] == "MOVE"]
    dupes = [p for p in plan if p["kind"] == "DUP"]
    renames = [p for p in plan if p["kind"] == "RENAME"]

    print(
        f"モード: {'APPLY' if args.apply else 'DRY-RUN'}  "
        f"map {len(mapping)} 件 / 実行 {len(plan)} 件"
        f"（移動 {len(moved)}・退避 {len(dupes)}・改名 {len(renames)}）"
    )
    for p in plan:
        mark = {"MOVE": "→", "DUP": "⇒temp", "RENAME": "→改名"}[p["kind"]]
        line = f"  [{p['kind']:<6}] {p['name']}  {mark}  {p['dest']}/{p['final']}"
        if p["note"]:
            line += f"   （{p['note']}）"
        print(line)
    for e in errors:
        print(f"  !! {e}")

    if not args.apply:
        if errors:
            print("dry-run で WARN/SKIP あり。map を修正してから --apply すること。")
            return 1
        print("dry-run 完了。問題なければ --apply で実行。")
        return 0

    log_rows = []
    for p in plan:
        dest_dir = os.path.join(vault, p["dest"])
        os.makedirs(dest_dir, exist_ok=True)
        target = os.path.join(dest_dir, p["final"])
        if os.path.exists(target):  # dry-run 後に状況が変わった場合の保険
            target = unique_target(target)
            p["final"] = os.path.basename(target)
        shutil.move(p["src"], target)
        rel = f"{p['dest']}/{p['final']}".replace(os.sep, "/")
        row = f"- [[{rel}|{p['final']}]]"
        if p["note"]:
            row += f" — {p['note']}"
        log_rows.append(row)
        print(f"  moved: {p['name']} → {rel}")

    if log_rows:
        os.makedirs(logs_dir, exist_ok=True)
        stamp = datetime.now(JST).strftime("%Y-%m-%d_%H%M")
        log_file = unique_log_path(logs_dir, stamp)
        content = (
            f"# 分類ログ\n"
            f"\n"
            f"`00_inbox` から各ディレクトリへ格納した記録（{now} 実行分）。\n"
            f"\n"
            f"## {now}（移動 {len(moved) + len(renames)} / 退避 {len(dupes)}）\n"
            f"\n"
            + "\n".join(log_rows)
            + "\n"
        )
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"ログ作成: {os.path.relpath(log_file, vault)}")
    print(f"完了: {now}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
