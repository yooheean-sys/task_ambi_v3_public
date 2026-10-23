---
name: hermes-desktop-app
description: "Use for Hermes desktop app how-to and feature questions."
version: 1.0.0
author: Hermes Agent (curator)
license: MIT
---
# Hermes Desktop App — answering how-to questions

## When to Use

- The user asks how to do something in the desktop app (settings, sessions, chats, sidebar) or where a UI element is.
- The user asks whether a Hermes feature exists.
- The user reports a chat/session behaving invisibly (archived/auto-archived/pinned/hidden flags).

Verify against docs + CLI + installed source before answering; give the exact Japanese UI labels the user sees.

## Procedure

1. **Docs index first.** `curl -s https://hermes-agent.nousresearch.com/docs/llms-full.txt > /tmp/llmsfull.txt` and grep it for the feature keyword. The index (`llms.txt`) maps "can Hermes do X" to its docs page, but `web_extract` truncates large pages — grepping a saved full copy is faster and lossless.
2. **Check the CLI surface.** `hermes <command> --help`. Some operations exist only in one direction (e.g. `hermes sessions archive` soft-hides; there is no `unarchive` subcommand — restore paths are UI-only). An absent CLI command is NOT evidence the feature is absent.
3. **Check live state.** Query `~/.hermes/state.db` with the Python `sqlite3` module inside `execute_code` (one call: `PRAGMA table_info(<table>)` then a filtered SELECT). Prefer this over a one-shot shell query — the schema and rows come back together and stay in the kernel for follow-ups.
4. **Get the UI facts from the installed source.** The source tree lives at `~/.hermes/hermes-agent`. Grep `apps/desktop/src` for the feature keyword to find which component owns it, then read the component to learn where the affordance lives (menu, settings page, filter toggle). Do not describe UI paths from memory or from the docs alone.
5. **Quote the exact labels.** Grep `apps/desktop/src/i18n/ja.ts` for the feature strings and give the user the same Japanese wording their app renders (e.g. 設定 → 「アーカイブ済みチャット」→「アーカイブを解除」). Paraphrased labels waste a round-trip when the user cannot find the button.
6. Only then answer. State which path you verified (docs / CLI / DB / source) so claims stay grounded.

## Pitfalls

- Never conclude "Hermes can't do that" without steps 1–4. The CLI and the docs lag the shipped app; the source tree is the ground truth for UI capabilities.
- Do not probe the user's running app via CDP to answer a UI question — the DevTools port opens only on dev-server runs, never on the packaged build the user runs. Grep the source instead. (Live DOM inspection in dev builds is covered by the `inspecting-hermes-desktop-dom` skill.)
- State-flag questions (why is a chat invisible?) — check the DB flags BEFORE suggesting UI surgery; the flags tell you whether it is archived, auto-archived, pinned, or hidden, and each has a different remedy. See `references/desktop-session-management.md`.
- Never hand-edit `state.db` to flip session flags when a UI path exists — UI actions go through the app's own API and stay consistent with its caches.
- Session toolsets freeze at session start: after `hermes mcp add` (or any config-driven tool change) the tools appear only in a NEW chat — the desktop slash palette has no `/reload-mcp` (typing it just returns a notice pointing at the CLI, which only refreshes that CLI session). The gateway connects the new MCP server from config within ~1 min regardless; browser-bridge specifics live in the `hermes-browser-automation` skill.

## Related

- `hermes-agent` skill (hub) — general Hermes orientation, spawning, theming.
- `inspecting-hermes-desktop-dom` skill — live DOM/CSS reads in dev-server builds only.
- `hermes-backend-ops` skill — serve/dashboard, gateway, kanban, cron.
