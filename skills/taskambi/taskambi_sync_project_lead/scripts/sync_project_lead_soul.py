#!/usr/bin/env python3
"""project_lead_* プロファイルの SOUL.md 共通節を点検・同期する。

構造契約:
  SOUL.md = 固有ヘッド + 共通節
  共通節     = 「## あなたは誰か」行から EOF（全 project_lead_* で同一であるべき部分）
  固有ヘッド = 冒頭〜その直前（タイトル / 担当プロジェクト / プロジェクトルートとディレクトリ参照）。
               原則プロジェクト固有だが、正本の LINE / BLOCK 仕様に該当する行は共通指示として同期する。

サブコマンド:
  check                      発散を報告する（読み取り専用・いつでも実行可）
  sync [--apply]             共通節を正本で上書きする（--apply 無しは dry-run・書き込まない）
  capture --from <profile>   指定プロファイルの現在内容から正本を再採録する

終了コード: 0=全クリーン / 1=発散あり（適用後も残存した場合を含む） / 2=構造エラー等で継続不能
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ANCHOR_HEADER = "## あなたは誰か"
DEFAULT_PROFILES_DIR = Path.home() / ".hermes" / "profiles"
DEFAULT_CANONICAL = Path(__file__).resolve().parent.parent / "references" / "project_lead_canonical.md"
MAX_DIFF_LINES = 40


class StructureError(Exception):
    """SOUL.md の構造が契約と違う（自動修復の対象にしない）。"""


# ---------------- 正本ファイル ----------------


@dataclass
class LineSpec:
    name: str
    required: bool
    excepted: frozenset
    anchor: str
    text: str


@dataclass
class BlockSpec:
    name: str
    required: bool
    excepted: frozenset
    anchor: str
    lines: list


@dataclass
class Canonical:
    tail_lines: list
    line_specs: list
    block_specs: list


def _parse_kv(rest: str):
    """"名前 required=yes except=a,b" 形式を解釈する。"""
    parts = rest.split()
    if not parts:
        raise ValueError("LINE/BLOCK 宣言に名前が無い")
    name = parts[0]
    required = False
    excepted = set()
    for kv in parts[1:]:
        if "=" not in kv:
            raise ValueError(f"不正なオプション「{kv}」（required=yes / except=a,b の形式）")
        k, v = kv.split("=", 1)
        if k == "required":
            required = (v == "yes")
        elif k == "except":
            excepted = {s.strip() for s in v.split(",") if s.strip() and s.strip() != "none"}
        else:
            raise ValueError(f"不明なオプション「{k}」")
    return name, required, frozenset(excepted)


def parse_canonical(path: Path) -> Canonical:
    raw = path.read_text(encoding="utf-8").split("\n")
    n = len(raw)
    i = 0
    tail_lines = None
    line_specs = []
    block_specs = []
    cur_line = None
    cur_block = None
    while i < n:
        line = raw[i]
        if line == "TAIL>>":
            if tail_lines is not None:
                raise ValueError("TAIL>> ブロックが2つある")
            j = i + 1
            buf = []
            while j < n and raw[j] != "<<TAIL":
                buf.append(raw[j])
                j += 1
            if j >= n:
                raise ValueError("TAIL>> に対応する <<TAIL が無い")
            while buf and buf[-1] == "":
                buf.pop()
            if not buf or buf[0].strip() != ANCHOR_HEADER:
                raise ValueError("TAIL>> ブロックの先頭は「## あなたは誰か」行であること")
            tail_lines = buf
            i = j + 1
            continue
        if line.startswith("BLOCK_TEXT>>"):
            j = i + 1
            buf = []
            while j < n and raw[j] != "<<BLOCK_TEXT":
                buf.append(raw[j])
                j += 1
            if j >= n:
                raise ValueError("BLOCK_TEXT>> に対応する <<BLOCK_TEXT が無い")
            if cur_block is None:
                raise ValueError("BLOCK_TEXT>> の前に BLOCK 宣言が必要")
            if not buf or not buf[0].startswith(cur_block.anchor):
                raise ValueError(f"BLOCK {cur_block.name}: ブロック先頭行が BLOCK_ANCHOR>> と前方一致しない")
            cur_block.lines = buf
            block_specs.append(cur_block)
            cur_block = None
            i = j + 1
            continue
        if line.startswith("LINE "):
            name, required, excepted = _parse_kv(line[len("LINE "):])
            cur_line = LineSpec(name, required, excepted, "", "")
            i += 1
            continue
        if line.startswith("ANCHOR>>"):
            if cur_line is None:
                raise ValueError("ANCHOR>> の前に LINE 宣言が必要")
            cur_line.anchor = line[len("ANCHOR>>"):].strip()
            if not cur_line.anchor:
                raise ValueError(f"LINE {cur_line.name}: ANCHOR>> が空")
            i += 1
            continue
        if line.startswith("TEXT>>"):
            if cur_line is None:
                raise ValueError("TEXT>> の前に LINE 宣言が必要")
            cur_line.text = line[len("TEXT>>"):].strip()
            if not cur_line.text:
                raise ValueError(f"LINE {cur_line.name}: TEXT>> が空")
            line_specs.append(cur_line)
            cur_line = None
            i += 1
            continue
        if line.startswith("BLOCK "):
            name, required, excepted = _parse_kv(line[len("BLOCK "):])
            cur_block = BlockSpec(name, required, excepted, "", [])
            i += 1
            continue
        if line.startswith("BLOCK_ANCHOR>>"):
            if cur_block is None:
                raise ValueError("BLOCK_ANCHOR>> の前に BLOCK 宣言が必要")
            cur_block.anchor = line[len("BLOCK_ANCHOR>>"):].strip()
            if not cur_block.anchor:
                raise ValueError(f"BLOCK {cur_block.name}: BLOCK_ANCHOR>> が空")
            i += 1
            continue
        i += 1  # コメント・空行・説明文は無視
    if cur_line is not None or cur_block is not None:
        raise ValueError("未完結の LINE / BLOCK 宣言がある")
    if tail_lines is None:
        raise ValueError("TAIL>> ブロックが無い")
    return Canonical(tail_lines, line_specs, block_specs)


CANONICAL_HEADER = """# project_lead 共通節 正本（taskambi_sync_project_lead）
# 全 project_lead_* プロファイルの SOUL.md 共通節の正本。編集は人間承認の上で行うか、
# capture --from <profile> で再採録する（capture は required/except の指定を保持する）。
#
# 書式:
#   TAIL>> ... <<TAIL              共通節本体（「## あなたは誰か」行から EOF まで）。全ファイルへそのまま適用
#   LINE <名前> required=yes|no except=<profile名,..|none>
#   ANCHOR>> <前方一致アンカー>     固有ヘッド内でこの接頭辞で始まる行を対象にする
#   TEXT>> <置き換え後の1行全文>
#   BLOCK <名前> required=yes|no except=...
#   BLOCK_ANCHOR>> <前方一致アンカー>
#   BLOCK_TEXT>> ... <<BLOCK_TEXT  ブロック全文（先頭行=アンカー行を含む。空白で字下げされた後続行も含む）
#
# required=yes : 全プロファイルに存在するべき（欠落は報告＝人間判断事項。自動挿入はしない）
# required=no  : 存在すれば同期、無ければ正常（例: 標準ディレクトリ構成の対象外プロジェクト）
# except=      : 意図的なプロジェクト差分を持つプロファイルを同期対象から除外する
"""


def serialize_canonical(can: Canonical) -> str:
    out = [CANONICAL_HEADER, "TAIL>>"]
    out.extend(can.tail_lines)
    out.append("<<TAIL")
    out.append("")
    for s in can.line_specs:
        out.append(f"LINE {s.name} required={'yes' if s.required else 'no'} except={','.join(sorted(s.excepted)) or 'none'}")
        out.append(f"ANCHOR>>{s.anchor}")
        out.append(f"TEXT>>{s.text}")
        out.append("")
    for b in can.block_specs:
        out.append(f"BLOCK {b.name} required={'yes' if b.required else 'no'} except={','.join(sorted(b.excepted)) or 'none'}")
        out.append(f"BLOCK_ANCHOR>>{b.anchor}")
        out.append("BLOCK_TEXT>>")
        out.extend(b.lines)
        out.append("<<BLOCK_TEXT")
        out.append("")
    return "\n".join(out)


# ---------------- SOUL 解析 ----------------


def rstrip_blank(lines):
    out = list(lines)
    while out and out[-1] == "":
        out.pop()
    return out


def split_soul(text: str):
    lines = text.split("\n")
    idx = [k for k, l in enumerate(lines) if l.strip() == ANCHOR_HEADER]
    if len(idx) != 1:
        raise StructureError(f"見出し「{ANCHOR_HEADER}」が {len(idx)} 個ある（ちょうど1個であること）")
    i = idx[0]
    if i == 0:
        raise StructureError("「## あなたは誰か」がファイル先頭にある（固有ヘッドが空）")
    head, tail = lines[:i], lines[i:]
    tail_h2 = {l.strip() for l in tail if l.startswith("## ")}
    dup = sorted(h for h in tail_h2 if any(l.strip() == h for l in head))
    if dup:
        raise StructureError("共通節の見出しが固有ヘッド側にも存在: " + ", ".join(dup))
    return head, tail


def find_index(lines, anchor):
    return next((k for k, l in enumerate(lines) if l.startswith(anchor)), -1)


def count_prefix(lines, anchor):
    return sum(1 for l in lines if l.startswith(anchor))


@dataclass
class Op:
    kind: str           # tail / line / block
    idx: int = -1
    old_span: int = 0
    new_lines: list = field(default_factory=list)
    label: str = ""


@dataclass
class Report:
    profile: str
    soul: Path
    head: list = field(default_factory=list)
    tail: list = field(default_factory=list)
    tail_drift: bool = False
    line_status: list = field(default_factory=list)   # (spec, status, idx)
    block_status: list = field(default_factory=list)  # (spec, status, idx, cur_lines)
    ops: list = field(default_factory=list)
    remaining: list = field(default_factory=list)
    error: str = ""


def evaluate(soul: Path, can: Canonical) -> Report:
    rep = Report(profile=soul.parent.name, soul=soul)
    head, tail = split_soul(soul.read_text(encoding="utf-8"))
    rep.head, rep.tail = head, tail
    rep.tail_drift = rstrip_blank(tail) != rstrip_blank(can.tail_lines)
    if rep.tail_drift:
        rep.ops.append(Op(kind="tail", label="共通節全体"))
    for spec in can.line_specs:
        idx = find_index(head, spec.anchor)
        if rep.profile in spec.excepted:
            status = "excepted"
        elif idx < 0:
            status = "missing" if spec.required else "absent"
            if spec.required:
                rep.remaining.append(f"LINE {spec.name}: アンカー行が見つからない（required・自動修復不可）")
        elif count_prefix(head, spec.anchor) > 1:
            status = "ambiguous"
            rep.remaining.append(f"LINE {spec.name}: アンカーに一致する行が複数ある・自動修復しない")
        elif head[idx] == spec.text:
            status = "ok"
        else:
            status = "drift"
            rep.ops.append(Op(kind="line", idx=idx, new_lines=[spec.text], label=f"LINE {spec.name}"))
        rep.line_status.append((spec, status, idx))
    for spec in can.block_specs:
        idx = find_index(head, spec.anchor)
        cur = []
        if rep.profile in spec.excepted:
            status = "excepted"
        elif idx < 0:
            status = "missing" if spec.required else "absent"
            if spec.required:
                rep.remaining.append(f"BLOCK {spec.name}: アンカー行が見つからない（required・自動修復不可）")
        else:
            j = idx + 1
            while j < len(head) and head[j].startswith(" "):
                j += 1
            cur = head[idx:j]
            if cur == spec.lines:
                status = "ok"
            else:
                status = "drift"
                rep.ops.append(Op(kind="block", idx=idx, old_span=len(cur),
                                  new_lines=list(spec.lines), label=f"BLOCK {spec.name}"))
        rep.block_status.append((spec, status, idx, cur))
    return rep


def apply_ops(rep: Report, can: Canonical) -> Path:
    new_head = list(rep.head)
    for op in sorted(rep.ops, key=lambda o: o.idx, reverse=True):
        if op.kind == "line":
            new_head[op.idx:op.idx + 1] = op.new_lines
        elif op.kind == "block":
            new_head[op.idx:op.idx + op.old_span] = op.new_lines
        elif op.kind == "tail":
            pass  # tail は全体差し替え
    content = "\n".join(new_head + rstrip_blank(can.tail_lines)) + "\n"
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = rep.soul.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f"SOUL.md.pre-sync-{ts}.md"
    shutil.copy2(rep.soul, backup)
    rep.soul.write_text(content, encoding="utf-8")
    return backup


def verify_after(rep: Report, can: Canonical):
    try:
        post = evaluate(rep.soul, can)
    except StructureError as e:
        return False, f"適用後の再点検で構造エラー: {e}"
    problems = []
    if post.tail_drift:
        problems.append("共通節が正本と一致しない")
    for spec, status, _idx in post.line_status:
        if status in ("drift", "ambiguous"):
            problems.append(f"LINE {spec.name}: {status}")
    for spec, status, _idx, _cur in post.block_status:
        if status in ("drift", "ambiguous"):
            problems.append(f"BLOCK {spec.name}: {status}")
    if problems:
        return False, "適用後も残存: " + "; ".join(problems)
    return True, ""


def unified(old_lines, new_lines, fromfile, tofile):
    d = list(difflib.unified_diff(old_lines, new_lines, fromfile=fromfile, tofile=tofile, lineterm=""))
    if len(d) > MAX_DIFF_LINES:
        d = d[:MAX_DIFF_LINES] + ["  …（diff 省略）"]
    return d


STATUS_JA = {
    "ok": "一致",
    "drift": "差分あり",
    "missing": "行が無い（required）",
    "absent": "行なし（required=no なので正常）",
    "excepted": "除外（意図的差分を保持）",
    "ambiguous": "アンカー重複（自動修復しない）",
}


def print_report(rep: Report, can: Canonical, show_diff: bool = True, brief: bool = False):
    if rep.error:
        print(f"■ {rep.profile}: 構造エラー → {rep.error}")
        print("  （このファイルは書き換えない。人間が確認すること）")
        return
    if brief:
        if not rep.ops and not rep.remaining:
            state = "発散なし"
        else:
            state = f"発散あり（自動修正 {len(rep.ops)}箇所 / 要人間対応 {len(rep.remaining)}件）"
        print(f"■ {rep.profile}: {state}")
        return
    fixes = len(rep.ops)
    head = f"■ {rep.profile}: " + ("発散なし" if fixes == 0 and not rep.remaining else f"発散あり（自動修正 {fixes}箇所）")
    print(head)
    if rep.tail_drift:
        print("  共通節（## あなたは誰か 以降）が正本と異なる:")
        if show_diff:
            for l in unified(rstrip_blank(rep.tail), rstrip_blank(can.tail_lines),
                             f"{rep.profile}:SOUL.md 共通節(現状)", "正本"):
                print("   " + l)
    for spec, status, idx in rep.line_status:
        print(f"  LINE {spec.name}: {STATUS_JA[status]}")
        if status == "drift" and show_diff:
            print(f"   - {rep.head[idx]}")
            print(f"   + {spec.text}")
    for spec, status, idx, cur in rep.block_status:
        print(f"  BLOCK {spec.name}: {STATUS_JA[status]}" + (f"（{len(cur)}行）" if status in ("ok", "drift") else ""))
        if status == "drift" and show_diff:
            for l in unified(cur, spec.lines, f"{rep.profile}:SOUL.md ブロック(現状)", "正本"):
                print("   " + l)
    for note in rep.remaining:
        print(f"  ※ {note}")


def summarize(reports) -> int:
    n_ops = sum(len(r.ops) for r in reports)
    n_rem = sum(len(r.remaining) for r in reports)
    errs = [r for r in reports if r.error]
    drifted = [r for r in reports if not r.error and (r.ops or r.remaining)]
    print(f"--- サマリ: プロファイル {len(reports)}件 / 発散あり {len(drifted)}件 / "
          f"自動修正可能 {n_ops}箇所 / 要人間対応 {n_rem}件 / 構造エラー {len(errs)}件")
    if errs:
        return 2
    if drifted:
        return 1
    return 0


# ---------------- サブコマンド ----------------


def load_canonical(args) -> Canonical:
    p = Path(args.canonical).expanduser()
    if not p.exists():
        print(f"エラー: 正本ファイルが無い: {p}\n  先に capture --from <profile> を実行してください", file=sys.stderr)
        raise SystemExit(2)
    can = parse_canonical(p)
    digest = hashlib.md5(p.read_bytes()).hexdigest()[:8]
    print(f"正本: {p} (md5 {digest} / 共通節 {len(can.tail_lines)}行・LINE {len(can.line_specs)}件・BLOCK {len(can.block_specs)}件)")
    return can


def discover(profiles_dir: Path, only: str):
    if not profiles_dir.is_dir():
        print(f"エラー: プロファイルディレクトリが無い: {profiles_dir}", file=sys.stderr)
        raise SystemExit(2)
    out = []
    for d in sorted(profiles_dir.iterdir()):
        if d.is_dir() and d.name.startswith("project_lead") and (d / "SOUL.md").is_file():
            if only and only not in d.name:
                continue
            out.append(d)
    return out


def evaluate_all(profiles, can):
    reports = []
    for d in profiles:
        soul = d / "SOUL.md"
        try:
            reports.append(evaluate(soul, can))
        except StructureError as e:
            reports.append(Report(profile=d.name, soul=soul, error=str(e)))
    return reports


def cmd_check(args) -> int:
    can = load_canonical(args)
    profiles = discover(Path(args.profiles_dir).expanduser(), args.only)
    if not profiles:
        print("エラー: 対象プロファイルが見つからない", file=sys.stderr)
        return 2
    reports = evaluate_all(profiles, can)
    print("=== project_lead_* SOUL.md 共通節点検（読み取り専用）")
    for rep in reports:
        print_report(rep, can)
    return summarize(reports)


def cmd_sync(args) -> int:
    can = load_canonical(args)
    profiles = discover(Path(args.profiles_dir).expanduser(), args.only)
    if not profiles:
        print("エラー: 対象プロファイルが見つからない", file=sys.stderr)
        return 2
    reports = evaluate_all(profiles, can)
    mode = "適用" if args.apply else "dry-run（書き込みなし）"
    print(f"=== project_lead_* SOUL.md 共通節同期（{mode}）")
    for rep in reports:
        print_report(rep, can)
    if not args.apply:
        print("--- dry-run: 書き込みは行っていない。適用するなら --apply を付けて再実行")
        return summarize(reports)
    done = 0
    for rep in reports:
        if rep.error or not rep.ops:
            continue
        backup = apply_ops(rep, can)
        ok, msg = verify_after(rep, can)
        if ok:
            done += 1
            print(f"● {rep.profile}: 適用完了（バックアップ: {backup}）")
        else:
            shutil.copy2(backup, rep.soul)
            print(f"● {rep.profile}: 適用後に検証失敗 → バックアップから復元: {msg}")
            return 2
    print("--- 適用後の最終点検")
    for rep in evaluate_all(profiles, can):
        print_report(rep, can, brief=True)
    return summarize(evaluate_all(profiles, can))


def cmd_capture(args) -> int:
    can_path = Path(args.canonical).expanduser()
    profiles_dir = Path(args.profiles_dir).expanduser()
    src = profiles_dir / args.from_profile / "SOUL.md"
    if not src.exists():
        print(f"エラー: 採録元が見つからない: {src}", file=sys.stderr)
        return 2
    head, tail = split_soul(src.read_text(encoding="utf-8"))
    new_tail = rstrip_blank(tail)
    if can_path.exists():
        old_can = parse_canonical(can_path)
        ts = time.strftime("%Y%m%d-%H%M%S")
        bak = can_path.parent / (can_path.name + f".pre-capture-{ts}.bak")
        shutil.copy2(can_path, bak)
        print(f"正本バックアップ: {bak}")
    else:
        old_can = Canonical(new_tail, [], [])
    new_can = Canonical(list(new_tail), [], [])
    for spec in old_can.line_specs:
        idx = find_index(head, spec.anchor)
        if idx < 0:
            print(f"警告: LINE {spec.name}: 採録元にアンカー行が無い。旧 TEXT を保持")
            new_can.line_specs.append(LineSpec(spec.name, spec.required, spec.excepted, spec.anchor, spec.text))
        else:
            new_can.line_specs.append(LineSpec(spec.name, spec.required, spec.excepted, spec.anchor, head[idx]))
    for spec in old_can.block_specs:
        idx = find_index(head, spec.anchor)
        if idx < 0:
            print(f"警告: BLOCK {spec.name}: 採録元にアンカー行が無い。旧ブロックを保持")
            new_can.block_specs.append(spec)
        else:
            j = idx + 1
            while j < len(head) and head[j].startswith(" "):
                j += 1
            new_can.block_specs.append(BlockSpec(spec.name, spec.required, spec.excepted, spec.anchor, head[idx:j]))
    can_path.parent.mkdir(parents=True, exist_ok=True)
    can_path.write_text(serialize_canonical(new_can), encoding="utf-8")
    digest = hashlib.md5(can_path.read_bytes()).hexdigest()[:8]
    print(f"正本を更新: {can_path} (md5 {digest} / 共通節 {len(new_tail)}行・LINE {len(new_can.line_specs)}件・BLOCK {len(new_can.block_specs)}件)")
    print("→ 全複製への反映は sync --apply を実行")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sync_project_lead_soul.py",
                                 description="project_lead_* SOUL.md 共通節の点検・同期",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES_DIR),
                        help="プロファイル群のディレクトリ（既定: ~/.hermes/profiles）")
    common.add_argument("--canonical", default=str(DEFAULT_CANONICAL),
                        help="正本ファイル（既定: スキル同梱 references/project_lead_canonical.md）")
    common.add_argument("--only", default="", help="ディレクトリ名部分一致で対象を絞る")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", parents=[common], help="発散を報告（読み取り専用）")
    sp = sub.add_parser("sync", parents=[common], help="共通節を正本で上書き（--apply で実書き込み）")
    sp.add_argument("--apply", action="store_true", help="実際に書き込む（無しは dry-run）")
    cp = sub.add_parser("capture", parents=[common], help="指定プロファイルから正本を再採録")
    cp.add_argument("--from", dest="from_profile", required=True, help="採録元プロファイルのディレクトリ名")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "sync":
        return cmd_sync(args)
    return cmd_capture(args)


if __name__ == "__main__":
    sys.exit(main())
