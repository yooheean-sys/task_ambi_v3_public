#!/usr/bin/env bash
# TEMPLATE: check/surface shell-hook pair (source: verified working on this machine).
# check   (post_tool_call, matcher "write_file|patch") → validates + records verdicts.
# surface (pre_llm_call) → injects the verdict batch into the next model turn, consumes it.
# Adapt: swap the mmdc render for any checker; keep the state-file handshake and
# the jq-only JSON building. Requires: jq, sha256sum, flock, timeout.
#
# Mine: edited file is .mmd/.mermaid (whole file) or .md containing ```mermaid
# fences (each fence rendered separately). Results cached by content sha256.

MODE="${1:-}"
[ -n "$MODE" ] || exit 0

HH="${HERMES_HOME:-$HOME/.hermes}"
BASE="$HH/agent-hooks/mermaid-check"
CACHE="$BASE/cache"
STATE="$BASE/state.jsonl"   # pending verdicts (consumed by surface)
LOG="$BASE/log.jsonl"       # append-only history of every verdict
LOCK="$BASE/.lock"
MAX_AGE=600        # surface drops state entries older than this (seconds)
RENDER_TIMEOUT=90
mkdir -p "$CACHE" || exit 0

# --- tool locator: hook env lacks nvm PATH, so re-resolve + prepend ----------
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
  export PATH="$MMDC_DIR:$PATH"   # mmdc shebang needs `node` on PATH
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
  [ -f "$FILE" ] || exit 0   # deleted → out of scope

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
          if (inblk) { inblk = 0; next }              # closing fence
          lower = tolower($0); sub(/^[[:space:]]*/, "", lower)
          if (lower ~ /^```mermaid/) { inblk = 1; idx++; next }
          next
        }
        inblk { printf "%s\n", $0 > (out "/block_" idx ".mmd") }
      ' "$FILE"
      for f in "$TMP"/block_*.mmd; do [ -f "$f" ] && BLOCKS+=("$f"); done
      [ ${#BLOCKS[@]} -gt 0 ] || { rm -rf "$TMP"; exit 0; }  # no mermaid blocks
      ;;
    *) rm -rf "$TMP"; exit 0 ;;
  esac

  n=0
  for bf in "${BLOCKS[@]}"; do
    n=$((n+1))
    if [ ! -s "$bf" ]; then
      _append_entry "toolwarn" "$FILE" "$n" "(empty mermaid block)" ""
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
        VERDICT="toolwarn"; MSG="mmdc(mermaid-cli) not found — render check skipped"
      else
        timeout "$RENDER_TIMEOUT" "$MMDC" -i "$bf" -o "$CSVG.tmp" -q 2>"$TMP/render.err"
        rc=$?
        if [ $rc -eq 0 ] && [ -s "$CSVG.tmp" ]; then
          mv "$CSVG.tmp" "$CSVG"
          VERDICT="ok"; MSG=""; SVG="$CSVG"
        else
          e1="$(grep -m1 -iE 'Parse error|Diagram error|Syntax error' "$TMP/render.err" 2>/dev/null | head -c 280 || true)"
          e2="$(grep -m1 'Expecting' "$TMP/render.err" 2>/dev/null | head -c 220 || true)"
          MSG="${e1:-}"
          [ -n "$e2" ] && MSG="${MSG}; ${e2}"
          [ -z "$MSG" ] && MSG="(mmdc exit=$rc $(head -c 160 "$TMP/render.err" 2>/dev/null))"
          case "$MSG" in
            *"Failed to launch"*|*"browser"*|*"Browser"*|*libGL*|*"No usable sandbox"*)
              VERDICT="toolwarn" ;;         # environment problem, not diagram syntax
            *)
              if [ $rc -eq 124 ]; then
                VERDICT="toolwarn"; MSG="render timed out (${RENDER_TIMEOUT}s)"
              else
                VERDICT="fail"
              fi ;;
          esac
          rm -f "$CSVG.tmp"
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
  : > "$STATE"     # consume the batch (stale entries dropped, not surfaced)
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
        CNT_OK=$((CNT_OK+1)); extra=""
        [ -n "$svg" ] && [ -f "$svg" ] && extra=" / SVG: $svg"
        CTX+=$'\n'"- OK: $pth (ブロック#${blk})${extra}" ;;
      fail)
        CNT_NG=$((CNT_NG+1))
        CTX+=$'\n'"- NG: $pth (ブロック#${blk}) — ${msg}" ;;
      *)
        CNT_WARN=$((CNT_WARN+1))
        CTX+=$'\n'"- 未確認: $pth (ブロック#${blk}) — ${msg}" ;;
    esac
  done
  CTX+=$'\n'"(合計: OK ${CNT_OK}件 / NG ${CNT_NG}件 / 未確認 ${CNT_WARN}件)"
  if [ "$CNT_NG" -gt 0 ]; then
    CTX+=$'\n'"→ NGのmermaid図を修正し、同じファイルに保存し直してください(保存時に自動で再検査されます)。修正中にこの警告への言及は不要です。"
  fi
  # line-based truncation (multibyte-safe; byte-count would cut UTF-8 mid-char)
  CTX="$(printf '%s\n' "$CTX" | head -14)"
  exec 9>&-
  [ -n "$CTX" ] && jq -n --arg c "$CTX" '{context: $c}'
  exit 0
fi

exit 0
