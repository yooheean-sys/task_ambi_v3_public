#!/usr/bin/env python3
"""taskambi-review.py — taskambi スキル使用セッションの自動行動履歴検査 hook

Hermes shell hooks (stdlib only)。config.yaml の on_session_end から呼ばれる。

modes:
  detect
      on_session_end。当該セッションの tool_calls に taskambi スキルの使用が
      あるかを session DB から検出し、あれば遅延検査プロセスを fire-and-forget
      で起動する。ユーザーがすぐ次のメッセージを送る場合は検査を中断する。
  delayed_review <session_id>
      detect から detach して起動される。IDLE_WAIT 秒待機し、その間に新規
      ユーザーメッセージがなければ専用スキル taskambi_conduct_review の
      検査プロセス（hermes chat one-shot --resume）を起動する。

無限ループ防止:
  検査プロセスは環境変数 HERMES_TASKAMBI_REVIEW=1 付きで起動される。
  detect はこの環境変数があれば即座に何もせず終了する。
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
BASE = HERMES_HOME / "agent-hooks" / "taskambi-review"
STATE = BASE / "state.jsonl"
LOG = BASE / "log.jsonl"
PENDING = BASE / "pending.json"
IDLE_WAIT_S = 120          # 検査起動前の idle 待機秒数
PENDING_STALE_S = 600      # pending がこれより古ければ破棄して再起動を許可
REVIEW_SKILL = "taskambi_conduct_review"

REVIEW_PROMPT_TEMPLATE = (
    "[taskambi 自動検査] このセッション（session_id={sid}）で taskambi スキル群が"
    "使用されました。専用スキル {skill} を読み込み（skill_view '{skill}'）、"
    "このセッションの行動履歴を session_search で取得して検査してください。"
    "検査観点: 使用された各 taskambi スキルの「してはいけないこと」「Pitfalls」"
    "「Verification」への適合と、SOUL/規約上の必須条項の遵守。"
    "想定通り動かなかった部分の改善事項を挙げ、自動適用可のものは修正、"
    "人間承認必要のものは報告して止まってください。"
)


def read_payload() -> dict:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_base():
    BASE.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, obj: dict):
    ensure_base()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def session_db_path() -> Path:
    """この hook が動いている profile の session DB を返す。

    default profile: HERMES_HOME/state.db
    named profile:   HERMES_HOME/profiles/<profile>/state.db
    HERMES_PROFILE 環境変数が無い場合は default を仮定する。
    """
    profile = (os.environ.get("HERMES_PROFILE") or "").strip()
    if profile:
        p = HERMES_HOME / "profiles" / profile / "state.db"
        if p.exists():
            return p
    return HERMES_HOME / "state.db"


def connect_ro(path: Path):
    uri = f"file:{path}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=10)


def extract_taskambi_skills(tool_calls_json) -> list:
    """tool_calls JSON から使用された taskambi スキル名を抽出する。

    対応する呼び出し形:
    - バッチラッパー tool_call の calls[].name が taskambi_ で始まる直接呼び
    - calls[].name == skill_view で arguments.name が taskambi_ で始まるもの
    - 単発 function.name が taskambi_ / skill_view のもの
    """
    skills = []
    if not tool_calls_json:
        return skills
    try:
        arr = json.loads(tool_calls_json)
    except Exception:
        return skills
    if not isinstance(arr, list):
        return skills

    def scan_args(name, args):
        if not isinstance(args, dict):
            return
        an = args.get("name", "")
        if name == "skill_view" and isinstance(an, str) and an.startswith("taskambi_"):
            if an not in skills:
                skills.append(an)
        if isinstance(name, str) and name.startswith("taskambi_") and name not in skills:
            skills.append(name)

    for call in arr:
        if not isinstance(call, dict):
            continue
        fn = call.get("function", {}) or {}
        fname = fn.get("name", "")
        args_raw = fn.get("arguments", "")
        if fname == "tool_call":
            try:
                batch = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:
                batch = {}
            calls = (batch.get("calls") or []) if isinstance(batch, dict) else []
            for c in calls:
                if isinstance(c, dict):
                    scan_args(c.get("name", ""), c.get("arguments", {}))
        else:
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:
                args = {}
            scan_args(fname, args)
    return skills


def session_taskambi_usage(sid: str):
    """(skills, last_msg_ts) を返す。スキルが使われていなければ ([], None)。"""
    dbp = session_db_path()
    if not dbp.exists():
        return [], None
    try:
        db = connect_ro(dbp)
    except Exception:
        return [], None
    rows = []
    try:
        rows = db.execute(
            "SELECT tool_calls, timestamp FROM messages "
            "WHERE session_id=? AND tool_calls IS NOT NULL AND length(tool_calls)>2 "
            "ORDER BY timestamp",
            (sid,),
        ).fetchall()
    except Exception:
        rows = []
    finally:
        try:
            db.close()
        except Exception:
            pass
    skills = []
    last_ts = None
    for tc, ts in rows:
        found = extract_taskambi_skills(tc)
        if found:
            for s in found:
                if s not in skills:
                    skills.append(s)
            if ts is not None and (last_ts is None or ts > last_ts):
                last_ts = ts
    return skills, last_ts


def read_state() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_state(st: dict):
    ensure_base()
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def read_pending() -> dict:
    if not PENDING.exists():
        return {}
    try:
        return json.loads(PENDING.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_pending(p: dict):
    ensure_base()
    PENDING.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")


def launch_review(sid: str):
    env = dict(os.environ)
    env["HERMES_TASKAMBI_REVIEW"] = "1"
    prompt = REVIEW_PROMPT_TEMPLATE.format(sid=sid, skill=REVIEW_SKILL)
    cmd = [
        "hermes",
        "--skills", REVIEW_SKILL,
        "--resume", sid,
        "--accept-hooks",
        "chat", "-q", prompt, "--oneshot",
    ]
    try:
        subprocess.Popen(
            cmd, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        append_jsonl(LOG, {"type": "review_launched", "session_id": sid, "ts": now_iso()})
        return True
    except Exception as e:
        append_jsonl(LOG, {"type": "review_launch_error", "session_id": sid,
                           "error": str(e), "ts": now_iso()})
        return False


def mode_detect():
    payload = read_payload()
    if os.environ.get("HERMES_TASKAMBI_REVIEW") == "1":
        # 検査プロセス内: 自己スキップ（無限ループ防止）
        return
    sid = payload.get("session_id") or ""
    if not sid:
        return
    skills, last_ts = session_taskambi_usage(sid)
    if not skills:
        return
    # 遅延検査が既に pending なら追加起動しない（stale なら破棄して再起動）
    pend = read_pending()
    if pend.get("session_id") == sid:
        try:
            age = time.time() - datetime.fromisoformat(pend["trigger_ts"]).timestamp()
            if age < PENDING_STALE_S:
                return
        except Exception:
            pass
    write_pending({"session_id": sid, "trigger_ts": now_iso(),
                   "last_msg_ts": last_ts, "skills": skills})
    cmd = [sys.executable, str(Path(__file__).resolve()), "delayed_review", sid]
    try:
        subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, cwd=str(BASE),
        )
        append_jsonl(LOG, {"type": "delay_launched", "session_id": sid,
                           "skills": skills, "ts": now_iso()})
    except Exception as e:
        append_jsonl(LOG, {"type": "delay_launch_error", "session_id": sid,
                           "error": str(e), "ts": now_iso()})
        write_pending({})


def mode_delayed_review(sid: str):
    pend = read_pending()
    last_msg_ts = pend.get("last_msg_ts")
    append_jsonl(LOG, {"type": "delayed_review_started", "session_id": sid, "ts": now_iso()})
    time.sleep(IDLE_WAIT_S)
    # 待機中に新規ユーザーメッセージが来たか確認（来たら作業継続中なので中断）
    new_user_msgs = 0
    dbp = session_db_path()
    if dbp.exists():
        try:
            db = connect_ro(dbp)
            try:
                if last_msg_ts is not None:
                    row = db.execute(
                        "SELECT COUNT(*) FROM messages WHERE session_id=? AND role='user' AND timestamp > ?",
                        (sid, last_msg_ts),
                    ).fetchone()
                    new_user_msgs = row[0] if row else 0
                else:
                    # last_msg_ts が無い（検出直後に起動された場合）: 直近5分の
                    # ユーザーメッセージがあれば中断とみなす
                    cutoff = pend.get("trigger_ts")
                    row = db.execute(
                        "SELECT COUNT(*) FROM messages WHERE session_id=? AND role='user' AND timestamp > ?",
                        (sid, cutoff),
                    ).fetchone()
                    new_user_msgs = row[0] if row else 0
            finally:
                db.close()
        except Exception:
            new_user_msgs = 0
    if new_user_msgs > 0:
        append_jsonl(LOG, {"type": "review_cancelled_new_activity",
                           "session_id": sid, "ts": now_iso()})
        write_pending({})
        return
    ok = launch_review(sid)
    st = read_state()
    st[sid] = {"last_review_ts": now_iso(), "skills": pend.get("skills", [])}
    write_state(st)
    write_pending({})
    append_jsonl(LOG, {"type": "review_done", "session_id": sid,
                       "launched": ok, "ts": now_iso()})


def main():
    args = sys.argv[1:]
    if not args:
        return
    mode = args[0]
    if mode == "detect":
        mode_detect()
    elif mode == "delayed_review" and len(args) >= 2:
        mode_delayed_review(args[1])


if __name__ == "__main__":
    main()
