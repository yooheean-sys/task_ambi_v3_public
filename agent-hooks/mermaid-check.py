#!/usr/bin/env python3
"""mermaid-check.py — Hermes shell hooks (stdlib only)

modes:
  check   post_tool_call (matcher write_file|patch)
          編集後にディスクへ落ちたファイルが mermaid を含む場合、mmdc で実際に
          描画して「プレビューできるか」を検証。結果を state.jsonl(未出力キュー)
          と log.jsonl(全履歴)へ記録。成功時は cache/<hash>.svg を残す。
  gate    pre_tool_call (matcher write_file|patch)
          書き込み前に「これから書かれる内容」を検証。NG なら exit 2 + JSON
          {"action":"block","message":...} でブロックし、エージェントは同一ターン
          内で修正できる。環境問題なら fail-open。
  surface pre_llm_call
          check の直近結果を {"context": ...} で返す(次ユーザーターン先頭に注入)。
"""
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HH = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
BASE = HH / "agent-hooks" / "mermaid-check"
CACHE = BASE / "cache"
STATE = BASE / "state.jsonl"
LOG = BASE / "log.jsonl"
LOCKP = BASE / ".lock"
MAX_AGE = 600
RENDER_TIMEOUT = 90
MAX_MSG = 280


def find_mmdc() -> str:
    for d in os.environ.get("PATH", "").split(os.pathsep):
        c = Path(d) / "mmdc"
        if c.is_file():
            return str(c)
    home = Path.home()
    if (home / ".nvm" / "versions" / "node").is_dir():
        bins = sorted((home / ".nvm" / "versions" / "node").glob("*/bin/mmdc"))
        if bins:
            return str(bins[-1])
    return ""


MMDC = find_mmdc()
if MMDC:
    os.environ["PATH"] = str(Path(MMDC).parent) + os.pathsep + os.environ.get("PATH", "")


def read_payload() -> dict:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def extract_mermaid_blocks(text: str) -> list[tuple[int, str]]:
    """(開始行番号, 本文) のリスト。md 中の ```mermaid 囲みを抽出。"""
    blocks: list[tuple[int, str]] = []
    inblk = False
    buf: list[str] = []
    start = 0
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^\s*```(.*)$", line)
        if m:
            if inblk:
                blocks.append((start, "\n".join(buf)))
                inblk, buf = False, []
                continue
            label = m.group(1).strip().lower()
            if label.startswith("mermaid"):
                inblk, buf, start = True, [], i
            continue
        if inblk:
            buf.append(line)
    if inblk and buf:
        blocks.append((start, "\n".join(buf)))
    return blocks


def render(src: str, dest: Path | None = None) -> tuple[bool | None, str, str]:
    """(True, '', dest_path) / (None=環境問題, msg, '') / (False=文法NG, msg, '')"""
    if not MMDC:
        return None, "mmdc(mermaid-cli)が見つからず描画検証をスキップ", ""
    BASE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(BASE)) as td:
        srcp = Path(td) / "in.mmd"
        outp = Path(td) / "out.svg"
        srcp.write_text(src, encoding="utf-8")
        try:
            r = subprocess.run(
                [MMDC, "-i", str(srcp), "-o", str(outp), "-q"],
                capture_output=True, text=True, timeout=RENDER_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return None, f"レンダがタイムアウト({RENDER_TIMEOUT}s) — 図が大きすぎるか環境問題", ""
        if r.returncode == 0 and outp.is_file():
            svg = outp.read_text(encoding="utf-8", errors="replace")
            if 'class="error-text"' in svg:  # mermaidは文法エラーでもexit 0でエラー表示SVGを出す
                bodies = re.findall(r'class="error-text"[^>]*>([^<]*)<', svg)
                bodies = [b for b in bodies if "mermaid version" not in b]
                msg = "Syntax error in text: " + " ".join(bodies) if bodies else "Syntax error in text (error-text SVG)"
                return False, msg[:MAX_MSG], ""
            if dest is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.replace(outp, dest)
                return True, "", str(dest)
            return True, "", ""
        err = ""
        for pat in (r"Error: Parse error.*", r"Error: Diagram error.*", r"Syntax error.*", r"^Error:.*"):
            m = re.search(pat, r.stderr or "", re.MULTILINE | re.IGNORECASE)
            if m:
                err = m.group(0).strip()
                break
        exp = re.search(r"^Expecting.*", r.stderr or "", re.MULTILINE)
        if exp:
            err = (err + "; " + exp.group(0).strip()) if err else exp.group(0).strip()
        msg = err[:MAX_MSG] if err else f"(mmdc exit={r.returncode} {(r.stderr or '')[:160]})"
        low = msg.lower()
        if "failed to launch" in low or "browser" in low or "libgl" in low or "sandbox" in low:
            return None, msg, ""  # 図の文法ではなく環境側の問題 → fail-open
        return False, msg, ""


def check_one(sess: str, tool: str, path: str, bno: int, src: str, bline: int, *, queue: bool = True) -> tuple[str, str]:
    """1ブロック検証 + 記録。戻り値は (verdict, message)。"""
    if not src.strip():
        append_entry(sess, tool, path, bno, bline, "toolwarn", "(空のmermaidブロック)", "", queue=queue)
        return "toolwarn", "(空のmermaidブロック)"
    h = hashlib.sha256(src.encode("utf-8")).hexdigest()
    cj, csvg = CACHE / f"{h}.json", CACHE / f"{h}.svg"
    verdict, msg, svg, cached = "toolwarn", "", "", False
    if cj.is_file():
        try:
            c = json.loads(cj.read_text(encoding="utf-8"))
            verdict, msg = c.get("verdict", "toolwarn"), c.get("message", "")
            svg = str(csvg) if verdict == "ok" and csvg.is_file() else ""
            cached = True
        except (json.JSONDecodeError, OSError):
            cached = False
    if not cached:
        verdict, msg, svg = render(src, csvg)
        if verdict is True:
            verdict, msg, svg = "ok", "", str(csvg)
        elif verdict is None:
            verdict, svg = "toolwarn", ""
        else:
            verdict, svg = "fail", ""
        try:
            cj.write_text(json.dumps({"verdict": verdict, "message": msg}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    append_entry(sess, tool, path, bno, bline, verdict, msg, svg, queue=queue)
    return verdict, msg


def append_entry(sess: str, tool: str, path: str, bno: int, bline: int, verdict: str, msg: str, svg: str, *, queue: bool = True) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": int(time.time()), "session_id": sess, "tool": tool, "path": str(path),
        "block": bno, "line": bline, "verdict": verdict, "message": msg, "svg": svg,
    }
    line = json.dumps(entry, ensure_ascii=False)
    with open(LOCKP, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        if queue:
            with open(STATE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def candidate_text(payload: dict) -> tuple[str, str] | None:
    """gate用:「これから書かれる全文」を返す。(テキスト, path) / 決定不能なら None"""
    tool = payload.get("tool_name") or ""
    ti = payload.get("tool_input") or {}
    path = str(ti.get("path") or "")
    cwd = str(payload.get("cwd") or "")
    if tool == "write_file":
        c = ti.get("content")
        return (str(c), path) if isinstance(c, str) else None
    if tool == "patch":
        old, new = ti.get("old_string"), ti.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str):
            return None
        p = Path(os.path.expanduser(path))
        if not p.is_absolute():
            p = Path(cwd) / p if cwd else p
        if not p.is_file():
            return None  # 新規作成patchは対象外(本来patchは存在ファイル向け)
        txt = p.read_text(encoding="utf-8", errors="replace")
        if ti.get("replace_all"):
            return txt.replace(old, new), path
        return txt.replace(old, new, 1), path
    return None


def lock_state_write(consumed: bool, kept: list[str]) -> None:
    with open(LOCKP, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        if consumed:
            STATE.write_text("".join(k + "\n" for k in kept), encoding="utf-8")


# --- modes -------------------------------------------------------------------
def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in {"check", "gate", "surface"}:
        return 0
    payload = read_payload()
    sess = str(payload.get("session_id") or "")

    if mode == "check":
        tool = str(payload.get("tool_name") or "")
        if tool not in {"write_file", "patch"}:
            return 0
        path = str((payload.get("tool_input") or {}).get("path") or "")
        p = Path(os.path.expanduser(path))
        if not p.is_absolute():
            cwd = str(payload.get("cwd") or "")
            p = (Path(cwd) / p) if cwd else p
        if not p.is_file() or p.stat().st_size > 300_000:
            return 0
        txt = p.read_text(encoding="utf-8", errors="replace")
        ext = p.suffix.lower()
        blocks = [(0, txt)] if ext in {".mmd", ".mermaid"} else extract_mermaid_blocks(txt) if ext in {".md", ".markdown"} else []
        for i, (bl, body) in enumerate(blocks, 1):
            check_one(sess, tool, str(p), i, body, bl)
        return 0

    if mode == "gate":
        tool = str(payload.get("tool_name") or "")
        if tool not in {"write_file", "patch"}:
            return 0
        cand = candidate_text(payload)
        if cand is None:
            return 0  # 決定不能 → fail-open
        txt, path = cand
        if len(txt) > 300_000:
            return 0
        if not MMDC:
            return 0
        blocks = [(0, txt)] if Path(path).suffix.lower() in {".mmd", ".mermaid"} else extract_mermaid_blocks(txt)
        if not blocks:
            return 0  # mermaidなし → 通常書き込み
        ng = []
        for i, (bl, body) in enumerate(blocks, 1):
            verdict, msg = check_one(sess, tool, str(path), i, body, bl, queue=False)
            if verdict == "fail":
                where = f"ブロック#{i}" + (f"(行{bl}付近)" if bl else "")
                ng.append(f"{where}: {msg}")
        if ng:
            body_txt = "\n".join(f"- {x}" for x in ng[:5])[:600]
            print(json.dumps({
                "action": "block",
                "message": f"mermaidプレビュー検査で失敗したため書き込みをブロックしました({len(ng)}ブロック):\n{body_txt}\n→ 上記エラー箇所を修正して再度書き込んでください。",
            }, ensure_ascii=False))
            return 2
        return 0

    if mode == "surface":
        if not STATE.is_file() or STATE.stat().st_size == 0:
            return 0
        now = int(time.time())
        with open(LOCKP, "a+") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            lines = [l for l in STATE.read_text(encoding="utf-8").splitlines() if l.strip()]
        fresh = []
        for l in lines:
            try:
                if now - int(json.loads(l).get("ts", 0)) <= MAX_AGE:
                    fresh.append(json.loads(l))
            except (json.JSONDecodeError, ValueError, OSError):
                pass
        lock_state_write(consumed=True, kept=[])
        if not fresh:
            return 0
        okc = sum(1 for d in fresh if d.get("verdict") == "ok")
        ngc = sum(1 for d in fresh if d.get("verdict") == "fail")
        wc = len(fresh) - okc - ngc
        ctx = "[mermaidプレビュー確認 (shell hook)]"
        for d in fresh[:12]:
            p = d.get("path", "")
            blk = d.get("block", 0)
            v, m, svg = d.get("verdict"), d.get("message", ""), d.get("svg", "")
            if v == "ok":
                extra = f" / SVG: {svg}" if svg and Path(svg).is_file() else ""
                ctx += f"\n- OK: {p} (ブロック#{blk}){extra}"
            elif v == "fail":
                ctx += f"\n- NG: {p} (ブロック#{blk}) — {m}"
            else:
                ctx += f"\n- 未確認: {p} (ブロック#{blk}) — {m}"
        ctx += f"\n(合計: OK {okc}件 / NG {ngc}件 / 未確認 {wc}件)"
        if ngc:
            ctx += "\n→ NGのmermaid図を修正し、同じファイルに保存し直してください(保存時に自動で再検査されます)。修正中にこの警告への言及は不要です。"
        print(json.dumps({"context": ctx}, ensure_ascii=False))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())