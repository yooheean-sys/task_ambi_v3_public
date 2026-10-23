#!/usr/bin/env bash
# Probe the availability matrix of the self-hosted (events_only) Langfuse.
# Prints PASS/FAIL per endpoint. Never prints credentials.
set -u
set -a; source ~/.hermes/.env >/dev/null 2>&1; set +a
: "${HERMES_LANGFUSE_PUBLIC_KEY:?HERMES_LANGFUSE_PUBLIC_KEY missing in ~/.hermes/.env}"
: "${HERMES_LANGFUSE_SECRET_KEY:?HERMES_LANGFUSE_SECRET_KEY missing in ~/.hermes/.env}"
: "${HERMES_LANGFUSE_BASE_URL:?HERMES_LANGFUSE_BASE_URL missing in ~/.hermes/.env}"
B="$HERMES_LANGFUSE_BASE_URL"; A="$HERMES_LANGFUSE_PUBLIC_KEY:$HERMES_LANGFUSE_SECRET_KEY"
DS=probe-delete-me-temp

probe() { # name method path [json_body]
  local name="$1" method="$2" path="$3" body="${4:-}" code
  if [ -n "$body" ]; then
    code=$(curl -s -m 8 -u "$A" -X "$method" "$B$path" -H 'Content-Type: application/json' -d "$body" -o /dev/null -w '%{http_code}')
  else
    code=$(curl -s -m 8 -u "$A" -X "$method" "$B$path" -o /dev/null -w '%{http_code}')
  fi
  case "$code" in
    2*) st=PASS ;;
    4*) st=FAIL ;;
    *)  st=ERR  ;;
  esac
  printf '%-24s %-6s %s  %s\n' "$name" "$method" "$code" "$st"
}

probe health           GET  /api/public/health
probe prompts-v2       GET  /api/public/v2/prompts
probe datasets-v2      POST /api/public/v2/datasets "{\"name\":\"$DS\"}"
probe dataset-items-v1 POST /api/public/dataset-items "{\"datasetName\":\"$DS\",\"input\":{\"probe\":true}}"
probe dataset-items-v2 POST /api/public/v2/dataset-items "{\"datasetName\":\"$DS\",\"input\":{\"probe\":true}}"
probe traces-read      GET  '/api/public/traces?limit=1'

echo
echo "note: dataset deletion is disabled on events_only (405); remove dataset '$DS' from the Langfuse UI."
