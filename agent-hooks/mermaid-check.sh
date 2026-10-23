#!/usr/bin/env bash
# mermaid-check.sh — Hermes shell hook
#
#   check   (post_tool_call, matcher "write_file|patch"):
#     編集直後のファイルが mermaid を含む場合 ( .mmd/.mermaid 全文、または
#     .md 中の ```mermaid 囲みブロック ) mmdc で実際に描画し「プレビューできるか」
#     を検証する。結果は state.jsonl (未出力キュー) と log.jsonl (全履歴) に記録。
#     描画成功時はSVGを cache/<hash>.svg に残す。内容は sha256 でキャッシュ。
#
#   surface (pre_llm_call):
#     state.jsonl に残った直近の検査結果を {"context": "..."} として stdout に
#     出力する (Hermesが次のユーザーメッセージに注入)。注入後は消費する。
#     NG (描画失敗) があれば修正指示文を添える。
#
# 対象外: terminal ツール経由 (sed 等) のファイル編集はフック対象外。

MODE="${1:-}"
[ -n "$MODE" ] || exit 0

HH="${HERMES_HOME:-$HOME/.hermes}"
BASE="$HH/agent-hooks/mermaid-check"
CACHE="$BASE/cache"
STATE="$BASE/state.jsonl"
LOG="$BASE/log.jsonl"
LOCK="$BASE/.lock"
MAX_AGE=600        # state エントリの鮮度 (秒)。古いものは落ちずに破棄
RENDER_TIMEOUT=90  # 1ダイアグラムあたりのレンダ上限 (秒)
mkdir -p "$CACHE" || exit 0

# --- mmdc 探索: PATHになければ nvm 配下を探す -------------------------------
_find_mmdc() {
  local c
  c="$(command -v mmdc 2>/dev/null || true)"
  if [ -z "$c" ]; then
    local d
    for d in "$(ls -d "$HOME"/.nvm/versions/node/*/bin/mmdc 2>/dev/null | sort -V | tail -1)"; do
      c="$d"
    done
  fi
  printf '%s' "$c"
}

MMDC="$(_find_mmdc)"
if [ -n "$MMDC" ]; then
  MMDC_DIR="$(cd "$(dirname "$MMDC")" && pwd)"
  export PATH="$MMDC_DIR:$PATH"   # mmdc の shebang が node を解決できるように
fi

_lock() { exec 9>>"$LOCK"; flock 9; }

_append_entry() { # $1=verdict $2=path $3=block $4=message $5=svg
  local now ts_entry
  now="$(date +%s)"
  ts_entry="$(jq -cn --argjson ts "$now" --arg sid "$SESSION_ID" --arg tool "$TOOL_NAME" \
    --arg path "$2" --argjson blk "${3:-0}" --arg v "$1" --arg msg "${4:-}" --arg svg "${5:-}" \
    '{ts:$ts, session_id:$sid, tool:$tool, path:$path, block:$blk, verdict:$v, message:$msg, svg:$svg}')"
  _lock
  printf '%s\n' "$ts_entry" >> "$STATE"
  printf '%s\n' "$ts_entry" >> "$LOG"
}

# --- check (post_tool_call) ---------------------------------------------------
if [ "$MODE" = "check" ]; then
  payload="$(cat)"
  SESSION_ID="$(jq -r '.session_id // ""' <<<"$payload" 2>/dev/null)"
  TOOL_NAME="$(jq -r '.tool_name // ""' <<<"$payload" 2>/dev/null)"

  case "$TOOL_NAME" in write_file|patch) ;; *) exit 0 ;; esac

  p="$(jq -r '.tool_input.path // empty' <<<"$payload" 2>/dev/null)"
  [ -n "$p" ] || exit 0
  cwd="$(jq -r '.cwd // ""' <<<"$payload" 2>/dev/null)"
  p="${p/#\~/$HOME}"
  if [[ "$p" != /* ]]; then
    [ -f "$p" ] || [ -n "$cwd" ] && p="$cwd/$p"
  fi
  FILE="$(readlink -f "$p" 2>/dev/null || printf '%s' "$p")"
  [ -f "$FILE" ] || exit 0   # 削除された場合は対象外

  EXT="$(printf '%s' "${FILE##*.}" | tr '[:upper:]' '[:lower:]')"
  TMP="$(mktemp -d "$BASE/work.XXXXXX")"

  BLOCKS=()
  case "$EXT" in
    mmd|mermaid)
      cp "$FILE" "$TMP/block_1.mmd"; BLOCKS=("$TMP/block_1.mmd")
      ;;
    md|markdown)
      awk -v out="$TMP" '
        /^[[:space:]]*```/ {
          if (inblk) { inblk = 0; next }              # 閉じフェンス
          lower = tolower($0); sub(/^[[:space:]]*/, "", lower)
          if (lower ~ /^```mermaid/) { inblk = 1; idx++; next }
          next
        }
        inblk { printf "%s\n", $0 > (out "/block_" idx ".mmd") }
      ' "$FILE"
      for f in "$TMP"/block_*.mmd; do [ -f "$f" ] && BLOCKS+=("$f"); done
      [ ${#BLOCKS[@]} -gt 0 ] || { rm -rf "$TMP"; exit 0; }  # mermaidブロックなし
      ;;
    *) rm -rf "$TMP"; exit 0 ;;
  esac

  n=0
  for bf in "${BLOCKS[@]}"; do
    n=$((n+1))
    # 空ブロックガード
    if [ ! -s "$bf" ]; then
      _append_entry "toolwarn" "$FILE" "$n" "(空のmermaidブロック)" ""
      continue
    fi
    HASH="$(sha256sum "$bf" | cut -d' ' -f1)"
    CJ="$CACHE/$HASH.json"; CSVG="$CACHE/$HASH.svg"
    VERDICT=""; MSG=""; SVG=""
    if [ -s "$CJ" ]; then
      VERDICT="$(jq -r '.verdict // "toolwarn"' "$CJ" 2>/dev/null)"
      MSG="$(jq -r '.message // ""' "$CJ" 2>/dev/null)"
      [ "$VERDICT" = "ok" ] && SVG="$CSVG"
    else
      if [ -z "$MMDC" ]; then
        VERDICT="toolwarn"; MSG="mmdc(mermaid-cli)が見つからず描画検証をスキップ"
      else
        timeout "$RENDER_TIMEOUT" "$MMDC" -i "$bf" -o "$TMP/out.svg" -q 2>"$TMP/render.err"
        rc=$?
        if [ $rc -eq 0 ] && [ -s "$TMP/out.svg" ]; then
          # mermaidは文法エラーでもexit 0で「error-text」入りSVGを出すことがある → SVG自体も検査
          if grep -q 'class="error-text"' "$TMP/out.svg"; then
            BODY="$(sed -n 's/.*class="error-text"[^>]*>\([^<]*\).*/\1/p' "$TMP/out.svg" | grep -v 'mermaid version' | head -2 | tr '\n' ' ' | head -c 280)"
            VERDICT="fail"
            if [ -n "$BODY" ]; then MSG="Syntax error in text: $BODY"; else MSG="Syntax error in text (error-text SVG)"; fi
          else
            mv "$TMP/out.svg" "$CSVG"
            VERDICT="ok"
            MSG=""
            SVG="$CSVG"
          fi
        else
          e1="$(grep -m1 -iE 'Parse error|Diagram error|Syntax error' "$TMP/render.err" 2>/dev/null | head -c 280 || true)"
          e2="$(grep -m1 'Expecting' "$TMP/render.err" 2>/dev/null | head -c 220 || true)"
          MSG="${e1:-}"
          [ -n "$e2" ] && MSG="${MSG}; ${e2}"
          [ -z "$MSG" ] && MSG="(mmdc exit=$rc $(head -c 160 "$TMP/render.err" 2>/dev/null))"
          case "$MSG" in
            *"Failed to launch"*|*"browser"*|*"Browser"*|*libGL*|*"No usable sandbox"*)
              VERDICT="toolwarn" ;;         # 図の文法ではなく検証環境側の問題
            *)
              if [ $rc -eq 124 ]; then
                VERDICT="toolwarn"; MSG="レンダがタイムアウト(${RENDER_TIMEOUT}s) — 図が大きすぎるか環境問題"
              else
                VERDICT="fail"
              fi ;;
          esac
        fi
      fi
      jq -cn --arg v "$VERDICT" --arg m "$MSG" '{verdict:$v, message:$m}' > "$CJ" 2>/dev/null || true
    fi
    _append_entry "$VERDICT" "$FILE" "$n" "$MSG" "$SVG"
  done
  rm -rf "$TMP"
  exit 0
fi

# --- surface (pre_llm_call) ---------------------------------------------------
if [ "$MODE" = "surface" ]; then
  [ -s "$STATE" ] || exit 0
  now="$(date +%s)"
  _lock
  mapfile -t LINES < "$STATE"
  : > "$STATE"     # 消費: 鮮度の切れたものも破棄
  FRESH=(); GOT=0
  for line in "${LINES[@]}"; do
    [ -n "$line" ] || continue
    ts="$(jq -r '.ts // 0' <<<"$line" 2>/dev/null)"
    if [ $((now - ts)) -le "$MAX_AGE" ]; then FRESH+=("$line"); GOT=$((GOT+1)); fi
  done
  [ "$GOT" -gt 0 ] || exit 0

  CNT_OK=0; CNT_NG=0; CNT_WARN=0
  CTX="[mermaidプレビュー確認 (shell hook)]"
  for line in "${FRESH[@]}"; do
    v="$(jq -r '.verdict' <<<"$line" 2>/dev/null)"
    pth="$(jq -r '.path' <<<"$line" 2>/dev/null)"
    blk="$(jq -r '.block // 0' <<<"$line" 2>/dev/null)"
    msg="$(jq -r '.message // ""' <<<"$line" 2>/dev/null)"
    svg="$(jq -r '.svg // ""' <<<"$line" 2>/dev/null)"
    case "$v" in
      ok)
        CNT_OK=$((CNT_OK+1))
        extra=""
        [ -n "$svg" ] && [ -f "$svg" ] && extra=" / SVG: $svg"
        CTX+=$'\n'"- OK: $pth (ブロック#${blk})${extra}"
        ;;
      fail)
        CNT_NG=$((CNT_NG+1))
        CTX+=$'\n'"- NG: $pth (ブロック#${blk}) — ${msg}"
        ;;
      *)
        CNT_WARN=$((CNT_WARN+1))
        CTX+=$'\n'"- 未確認: $pth (ブロック#${blk}) — ${msg}"
        ;;
    esac
  done
  CTX+=$'\n'"(合計: OK ${CNT_OK}件 / NG ${CNT_NG}件 / 未確認 ${CNT_WARN}件)"
  if [ "$CNT_NG" -gt 0 ]; then
    CTX+=$'\n'"→ NGのmermaid図を修正し、同じファイルに保存し直してください(保存時に自動で再検査されます)。修正中にこの警告への言及は不要です。"
  fi
  # 送出は行数ベースで抑制 (マルチバイト安全化)
  CTX="$(printf '%s\n' "$CTX" | head -14)"
  exec 9>&-
  [ -n "$CTX" ] && jq -n --arg c "$CTX" '{context: $c}'
  exit 0
fi

exit 0