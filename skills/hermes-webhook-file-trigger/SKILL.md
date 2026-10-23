---
name: hermes-webhook-file-trigger
description: Use when building a file-drop webhook trigger on WSL.
---

# Webhook file-trigger pattern on WSL (vtt-minutes reference setup)

> 注記: vtt-minutes ルートの現在仕様は deliver=log（議事録を vault 00_inbox に保存する方式）。
> 運用・改修・テストの詳細は vault/vault_vtt_minutes スキルへ移管。本スキルは汎用パターンの解説。

## Why not inotify
WSL2 drvfs mounts (/mnt/c) do NOT propagate inotify events — a native watcher sees nothing.
Instead: cron `--no-agent` scan script (every 2m) → detects new files → POSTs to a local
webhook route → webhook agent does the work. Zero custom daemons; survives restarts.

## Setup (proven 2026-10-05)

1. Enable webhook platform:
   - `.env`: `WEBHOOK_ENABLED=true`, `WEBHOOK_PORT=8644`, `WEBHOOK_SECRET=<openssl rand -hex 32>`
   - ALSO `hermes config set platforms.webhook.enabled true` + `platforms.webhook.extra.port 8644`
     (the `hermes webhook` CLI checks config.yaml only — .env alone → CLI says "not enabled")
   - `hermes gateway restart`; verify `curl localhost:8644/health`
2. `hermes webhook subscribe <name> --prompt "..." --deliver discord --deliver-chat-id <id>`
   Secret is auto-generated, stored in ~/.hermes/webhook_subscriptions.json (there is NO "url" key —
   derive it: `http://localhost:<port>/webhooks/<name>`).
3. CRITICAL: webhook-spawned agent sessions get a minimal toolset — no file tools by default
   (agent flails in tool_search and fails). Fix: manually add a `"toolsets": ["file", "terminal"]`
   key to the route in ~/.hermes/webhook_subscriptions.json. Deliberately NOT settable via
   `hermes webhook subscribe` (agents must not self-grant tools). Hot-reloads on next POST.
4. Prompt must say: output the deliverable as your FINAL response — the system auto-delivers it;
   never call discord/send_message or CLI to send (causes double delivery / wrong channel).
5. Scan script in ~/.hermes/scripts/ (cron --script requires that dir), state file for seen files.
   First run = baseline (mark existing files seen, don't fire). Mark a file seen ONLY after
   successful POST (failed POSTs retry next tick). Skip files with mtime age < ~15s (still copying).
   Empty stdout / `[SILENT]` = silent; use `--deliver local`, `--failure-deliver` for error visibility.
6. Cron: `hermes cron create "*/2 * * * *" --no-agent --script <name>.py --deliver local --failure-deliver discord:<chat_id>`

## HMAC signing (generic V2)
`X-Webhook-Timestamp: <unix-sec>` + `X-Webhook-Signature-V2: hex(HMAC-SHA256(secret, "<ts>." + body))`.
Replay window enforced — timestamps must be fresh. V1 (body-only) is deprecated.

## Debugging
- gateway.log lines tagged `[webhook]` show POST/署名/response; `response ready ... response=N chars`
- Session transcripts in state.db (sessions/messages tables, join on sessions.id = messages.session_id;
  session_key ends with route name) — empty assistant content rows are tool-call turns, check other rows
- Cron script failures: executions.db `error` column has the stderr traceback
- Deleting the whole scan state file re-baselines (suppresses existing files) — remove single entries instead