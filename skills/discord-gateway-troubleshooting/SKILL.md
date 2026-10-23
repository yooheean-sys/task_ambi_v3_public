---
name: discord-gateway-troubleshooting
description: Use when the Discord gateway is silent or deaf.
---

# Discord gateway troubleshooting (verified 2026-10-05)

## When to Use
- Discord bot stopped replying or no inbound messages arrive on the gateway.
- Configuring `DISCORD_ALLOWED_USERS` / allowlist, or debugging mention handling.

Environment: bot `<discord-bot>` (user id <discord-user-id>) in guild「<discord-guild>」; gateway runs as systemd user service `hermes-gateway.service`; allowlist `DISCORD_ALLOWED_USERS=<discord-allowed-user-id>` (numeric user ID) in the profile secrets file (~/.hermes/.env).

## Pitfall 1 — empty allowlist fails closed
- `DISCORD_ALLOWED_USERS` entries that are NOT numeric get resolved against guild members at connect; unresolved username entries silently vanish -> empty allowlist -> every message denied. Only symptom: one WARNING in gateway.log: "no allowlist is configured".
- Fix: put the NUMERIC user ID (copy via Discord dev-mode right-click). `client_id` from the dev portal is the BOT's id, not the user's — don't mix them up.
- Adapter accepts `<@123>` / `user:123` prefixes via _clean_discord_id.

## Pitfall 2 — gateway goes deaf while process stays alive
- Symptom: TCP to Discord stays ESTAB, no disconnect logs, but zero inbound messages and periodic housekeeping logs stop (idle state can also log nothing — check last `inbound message` timestamp instead).
- Fix: `hermes gateway restart` (worked every time). Deep diagnosis: `sudo env "PATH=$PATH" py-spy dump --pid <pid>` (py-spy needs sudo in WSL here).
- NEVER run `hermes gateway run` in foreground while the systemd service is active — double bot-token connections conflict.

## Pitfall 3 — role mention instead of user mention (biggest trap)
- Discord auto-creates a managed role named after the bot (managed=True, name follows bot username, NOT renamable server-side). Mention autocomplete shows BOTH the bot member and that role.
- Adapter's `_self_is_explicitly_mentioned` only matches USER mentions (`<@botid>` / message.mentions). A role mention (`<@&roleid>`) is silently ignored — no inbound log at all.
- Verify via REST as the bot: GET /channels/{id}/messages — check content for `<@&` and whether `mentions` contains the bot user id.
- User-facing rule: pick the APP/BOT-badged entry (server nickname「アブリ」) in the mention autocomplete, not the same-named role.

## Diagnostics quick flow
1. `hermes gateway status` (active does not mean healthy)
2. `tail ~/.hermes/logs/gateway.log` — allowlist warning? recent `inbound message`?
3. `grep discord.gateway ~/.hermes/logs/agent.log | tail` — WS connect/RESUMED
4. REST-check mention format (pitfall 3 snippet)
5. `hermes gateway restart`, retest

## Misc facts
- Replies land in an AUTO-CREATED THREAD per conversation (auto-renamed), not the channel body — easy to miss on mobile.
- Bot replies are triggered by mention only in channels; DM path is separate.
- Voice playback disabled (no Opus); text unaffected.
- Logs: ~/.hermes/logs/gateway.log (gateway), agent.log (discord.py detail), journalctl --user -u hermes-gateway.service.
- Full user-facing guide written at ~/discord-guide.md.
