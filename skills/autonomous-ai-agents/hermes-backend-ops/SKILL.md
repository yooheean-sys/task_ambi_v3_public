---
name: hermes-backend-ops
description: "Use for Hermes serve/dashboard, the Discord/messaging gateway, kanban boards, or scheduled cron delivery jobs."
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, serve, dashboard, desktop, kanban, gateway, discord, messaging]
---

# Hermes Backend Ops — serve / dashboard / desktop, and the kanban board

Companion to the bundled `hermes-agent` skill (which routes topics to its own
references and the official docs). This skill holds the operational workflow and
mechanics verified against the installed source (`~/.hermes/hermes-agent`) and
live CLI behavior. When facts here conflict with the installed version, trust a
fresh `hermes <cmd> --help` / source grep over this file.

Covers also the desktop app's relationship to these backends.

## When to Use

- The user asks how to run/view the web dashboard, the headless backend, or the
  desktop app, or reports conflicts between them (port in use, "web UI
  disabled", dashboard refusing to start).
- The user wants to use, demo, or inspect the kanban task board — creating
  tasks, wiring parent/child dependencies, watching workers run.
- Any "can Hermes do X on the desktop app / dashboard?" surface question that
  the bundled `hermes-agent` hub leaves to verification.
- The user reports a messaging-platform problem (Discord bot not replying,
  messages denied/ignored, gateway up/down) — see the Discord gateway section.
- The user wants a recurring/scheduled agent task or a daily digest delivered
  to a chat platform — see Scheduled delivery jobs (cron).

## One server process, two modes

`hermes serve` and `hermes dashboard` front the SAME machine-level backend; a
second launch attaches to the running one instead of starting a new process.

- `hermes serve` is the HEADLESS backend: it sets `HERMES_SERVE_HEADLESS=1` and
  then never serves the browser SPA — only JSON-RPC/WebSocket/API. Opening the
  port in a browser shows "Headless backend (hermes serve): web UI disabled".
- `hermes dashboard` is the same server PLUS the browser UI. One server per host
  by default (`--isolated` opts out).
- Check what is running: `hermes dashboard --status` (lists "hermes
  dashboard/serve process(es)" with PID and argv).

Decision points:
- Need the web UI while a headless `serve` owns the host? `hermes dashboard`
  REFUSES with "Refusing to start: this host is already served by ... headless
  `hermes serve` backend with no dashboard UI." Never try to force it on the
  same port; instead run `hermes dashboard --isolated --port <other>` for a
  dedicated UI server alongside, or stop serve (`hermes serve --stop`) and run
  plain `hermes dashboard` when the headless backend isn't needed.
- `--stop` / `--status` flags exist on BOTH commands and manage the same
  process pool.

## Desktop app relationship

- The desktop app is SELF-CONTAINED: `hermes desktop` spawns its own `hermes
  serve` backend. It never requires the web dashboard, and serve/dashboard
  choices elsewhere don't block it — running `hermes serve` in parallel is
  compatible, not a conflict.
- Remote connection mode (Settings → Gateways → Remote gateway) attaches to a
  `hermes serve` process the user keeps running; the app does not start that
  one for them.
- The desktop app has NO kanban pane. Web UI for kanban lives in the dashboard.

## Auth gate

A bind on a non-loopback host (e.g. `--host 0.0.0.0`) always requires an auth
provider (password or OAuth) since the June 2026 hardening. `--insecure` is a
deprecated no-op. Tell the user to expect a login prompt when opening a
publicly bound server in a browser.

Basic-auth login is a credential FORM, not HTTP Basic headers: `curl -u
user:pass` returns 401 on protected APIs even with correct credentials — the
browser gets a sign-in page instead. Probe the gate on a protected endpoint
(`curl /api/sessions` → 401 without a session cookie); `/api/status` is a
PUBLIC endpoint that always answers 200, so a 200 there proves nothing about
auth.

## Remote access from another LAN device (WSL2)

Verified path, in order:

1. Bind the dashboard publicly: `hermes dashboard --isolated --port 9120
   --host 0.0.0.0`. The auth gate needs a provider — basic-auth via
   `HERMES_DASHBOARD_BASIC_AUTH_USERNAME/PASSWORD` in `$HERMES_HOME/.env` is
   the zero-setup option (see Auth gate above).
2. Punch through WSL2 NAT — a WSL-side `0.0.0.0` bind is NOT reachable from
   the LAN by itself. On Windows (admin PowerShell; a UAC prompt appears):
   ```powershell
   netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=9120 connectaddress=<WSL_IP> connectport=9120
   New-NetFirewallRule -DisplayName "Hermes Dashboard 9120" -Direction Inbound -LocalPort 9120 -Protocol TCP -Action Allow
   ```
   WSL IP: `ip addr show eth0` (from WSL). Windows LAN IP:
   `Get-NetIPAddress -AddressFamily IPv4`. Repeat both lines for the serve
   port (9119) if desktop-app remote-gateway access is wanted too.
3. Verify end-to-end from WSL by curling the Windows LAN IP
   (`http://<win-lan-ip>:9120/login` → 200) — one shot that exercises
   portproxy + firewall + the WSL listener. Do not declare success from the
   loopback check alone; it skips the Windows hop.

Pitfalls:
- The WSL eth0 IP changes on reboot and a stale portproxy silently times out
  from the LAN. After any WSL restart, re-check `ip addr show eth0` and re-run
  the portproxy lines with the new IP (delete + re-add the rule).
- `hermes dashboard --stop` stops the WHOLE web-server pool — the headless
  `serve` process included. To rebind one process, kill its PID from
  `hermes dashboard --status` and relaunch it with new flags.
- An agent-spawned long-lived server must run under
  `terminal(background=true, persist_on_release=true)` — a plain background
  process is killed by session cleanup when the chat ends.

## Discord / messaging gateway

The messaging gateway (Discord, Telegram, ...) is a SEPARATE process from
serve/dashboard: `hermes serve` + `hermes dashboard` running does NOT mean the
gateway is up. Check `hermes gateway status`; restart with `hermes gateway
restart`. On this host it runs as the systemd user unit
`hermes-gateway.service` (survives logout). Never start a foreground `hermes
gateway run` while the service is active — one bot token, two competing
connections.

Allowlist (fail-closed — with no allowlist configured, ALL messages are
silently denied):
- Put NUMERIC user IDs in `DISCORD_ALLOWED_USERS` (profile `.env`); the user
  copies theirs via Discord → User Settings → Advanced → Developer Mode →
  right-click own name → Copy User ID.
- Username entries are resolved against guild members only at connect time; an
  unmatched username silently empties the allowlist. The "messages are being
  denied because no allowlist is configured" warning logs ONCE per adapter
  instance — its absence does NOT mean messages are being admitted.
- After any allowlist/gate change, `hermes gateway restart` and confirm the
  `✓ discord connected` line in `~/.hermes/logs/gateway.log` before testing.
- The allowlist is per Discord ACCOUNT: the same numeric ID works from phone
  and PC.

"Bot is deaf" debugging, in order:
1. `tail ~/.hermes/logs/gateway.log` — every admitted message produces an
   `inbound message:` line. No inbound line = the message never passed the
   adapter gate or never arrived; nothing about the agent turn is relevant yet.
2. The Discord WebSocket can be ESTAB at TCP level and still be delivering
   nothing. Force a clean session with `hermes gateway restart` before deeper
   debugging; check `~/.hermes/logs/agent.log` for `discord.gateway`
   connect/RESUMED lines.
3. Ask HOW the user mentioned the bot. The gate fires only on a USER mention
   (`<@bot-id>`); a same-named ROLE mention (`<@&role-id>`) is silently
   ignored, and Discord's @ autocomplete offers BOTH when the server has a
   bot-named role. Verify the literal mention form via REST: read the bot
   token from the profile `.env` without printing it, then `GET
   /channels/<channel-id>/messages?limit=5` — shows the real message content
   (`<@&...>` vs `<@...>`) and whether the message exists at all. REST calls
   need a User-Agent header or Discord returns 403.
4. Adapter `print()` output (username resolution, allowlist rewrites) goes to
   stdout/journald only, never the log files — check `journalctl --user -u
   hermes-gateway.service`.
5. Deep runtime inspection needs elevated py-spy (`sudo env "PATH=$PATH"
   py-spy dump --pid <pid>`); without sudo, restart is the practical move.

Behavior notes for the user-facing explanation: channel messages require an
explicit mention of the bot; each conversation auto-creates a Discord thread
and replies land INSIDE the thread, which is easy to miss on mobile. Voice
channel playback stays disabled unless Opus is installed (startup warning);
text features are unaffected.

## Scheduled delivery jobs (cron)

Verified end-to-end on this host (job creation, manual fire, Discord delivery).
Create with `hermes cron create "<schedule>" --name <name> --deliver <target>
"<prompt>"` — the verb is `create` (there is no `add`); schedules accept local-TZ
cron expressions, durations ("30m"), or "every monday 9am". Cron expressions
evaluate in the HOST local timezone: run `date` before turning "毎朝" into
`0 8 * * *`, then confirm the returned "Next run" timestamp is what the user
meant.

- The job prompt must be SELF-CONTAINED: the cron session starts fresh with
  only that text. State the output language, format (headings / summaries /
  source URLs), and source discipline (dedupe, prefer confirmed reports)
  explicitly.
- Delivery targets use `platform:chat_id` grammar — e.g.
  `discord:<channel_id>`, or `origin` (back to a chat the job was created
  from) / `local` (save to `~/.hermes/cron/output/`).
- Resolve Discord channel IDs by grepping `~/.hermes/sessions/sessions.json`
  for `Source: Discord`: the stored context_prompt carries guild, parent-
  channel and thread IDs plus channel names. Do NOT discover IDs by calling
  the Discord REST API from ad-hoc commands — the bot token ends up on a
  command line (approval gate) and direct calls can 403. Only channels with
  an existing bot session appear in sessions.json; for a brand-new target
  channel the user mentions the bot there once, then re-grep.
- Scheduled fires need the gateway/backend running; if the host was down at
  fire time the run is skipped, not queued.
- Test immediately with `hermes cron run <id>` (runs in the background, takes
  ~1–2 min). Verify the DELIVERY, not just completion: `hermes cron runs <id>`
  shows the execution status, and the row in `~/.hermes/cron/executions.db`
  (column `delivery_outcome`) is ground truth — `delivered` vs `failed`. The
  rendered message is saved under `~/.hermes/cron/output/<job-id>/` for
  content review without asking the user to screenshot Discord.
- Jobs are per-profile: the gateway ticks each profile's scheduler separately
  ("Cron scheduler will tick N profile(s)" in gateway.log). Confirm
  `hermes cron list` shows the job under the ACTIVE profile with the expected
  Next run and Deliver line.
- `--script` (+ `--no-agent`) makes the job a pure scheduled script run with
  zero LLM cost; `--model`/`--provider` override per job. Pause/resume/remove
  exist as subcommands — confirm exact names against `hermes cron --help`.

## Kanban board operations

Board data is `~/.hermes/kanban.db` (init idempotently with `hermes kanban
init`). Four front doors: `hermes kanban <verb>` CLI, `/kanban` slash command,
dashboard UI, and the `kanban_*` toolset for workers.

Day-to-day verbs (read the board with the `list` subcommand): `create`,
`show`, `comment`,
`complete`, `block`/`unblock`, `edit`, `assign`, `stats`, `watch` (live event
stream), `tail <id>` (per-task stream), `dispatch`, `archive`.
Also shipped (confirm against `--help` on the installed version): `boards`
(one board per project; operate via `--board <slug>` or
`boards create|switch|list|rm`), `swarm` (built-in parallel-workers →
verifier → synthesizer graph), `decompose`/`specify` (auxiliary-LLM
task-graph generation and triage promotion),
`request-review`/`request-changes`/`reopen-review` (same-card review loop),
`link`/`unlink`, `promote`, `set-model` (per-task model/provider override).

Sample/demo task recipe (proven working) — fan-out-then-join:
```bash
hermes kanban create "<worker A>" --body "<contract>" --assignee <profile>
hermes kanban create "<worker B>" --body "<contract>" --assignee <profile>
A=<id from output>; B=<id from output>
hermes kanban create "<integrator>" --body "<merge contract>" --assignee <profile> \
  --parent "$A" --parent "$B"
hermes kanban create "<standalone>" --assignee <profile>
```
- `--parent P` means "this task is a CHILD of P and stays `todo` until P
  completes". The DEPENDENT task takes `--parent`; the dependency is never
  wired from the coordinator down. Wiring the integrator as the PARENT of its
  workers deadlocks — the workers wait for it while it waits for them — and a
  good worker will detect this and self-block with `kind: needs_input` instead
  of spinning.
- For a plain fan-out (no join), give the workers no parent at all; they run
  in parallel immediately.
- `--json` on create prints the full task record (the plain output prints only
  the id + status). Capture the id from whichever form you used.
- With the gateway running, the dispatcher (default `dispatch_in_gateway:
  true`) auto-claims ready tasks and spawns worker processes immediately — a
  freshly created task can be `running` within seconds. Don't assume tasks sit
  in `ready` for the user to dispatch manually.
- Write task bodies as a worker contract: what to produce and WHERE to put the
  result (task comments are the default handoff medium).
- **Inert org skeleton — build a hierarchy without spending a token:** create
  the root with `--triage` (parks it in `triage`; only the specifier promotes
  it, so the dispatcher never claims it) and each child with
  `--parent <previous>` (children stay `todo` while the parent is open).
  Verified safe even with the gateway dispatcher live. Verify the chain with
  `list` + `stats`, then promote/specify stage by stage once real persona
  profiles exist. Use this instead of the live fan-out recipe whenever the
  goal is to demonstrate or validate a structure, not to run work.
- Mapping an external hierarchical org design (custom YAML personas/stages,
  CrewAI-style role plans) onto these primitives: procedure + gap-analysis
  checklist in `references/mapping-external-org-designs.md`.

Pitfalls:
- Scratch workspaces are EPHEMERAL — deleted when the task completes. Any task
  whose worker output must survive as files needs `--workspace dir:/abs/path`
  (existing dir) or `--workspace worktree:` (git worktree).
- Re-dAG an existing dependency with `hermes kanban unlink <parent> <child>`
  then `hermes kanban link <new-parent> <new-child>`; a task freed from its
  last open parent flips to `ready` on its own. `promote` only lifts
  `todo`/`blocked` tasks — it errors on `ready`.
- Circuit breaker: the dispatcher auto-BLOCKS a task after `failure_limit`
  (default 2) consecutive spawn crashes, so a board left unattended ends with
  silent `blocked` cards. `hermes kanban show <id>` events carry the worker's
  stderr (`crashed` → `gave_up` with `worker_output`). Diagnose and fix the
  root cause FIRST, then `hermes kanban unblock <id> ...` to re-queue —
  unblocking without a fix just burns the retries again.
- Kanban workers are FRESH processes that read `$HERMES_HOME/.env` — a
  provider key that only exists in a parent process's environment (credential
  pool source `env:VAR`, common when a desktop-spawned backend registered it)
  does NOT reach spawned workers; they die at startup with "No API key found
  for provider X". Persist the key in `~/.hermes/.env`; the value can be moved
  without ever displaying it by reading `/proc/<backend-pid>/environ` and
  appending the matching line (back up `.env` first, keep it mode 600).
- When a task blocks itself with `kind: needs_input`, the worker found a
  design flaw (circular dependency, impossible contract) and usually proposes
  the fix in the block reason. Read it via `show`, correct the DAG or contract,
  comment the corrected instructions onto the task, then unblock.
- Non-ASCII titles can come out garbled when composed in a non-target language
  (e.g. CJK input producing Chinese characters) — proofread created titles and
  fix with `hermes kanban edit <id> --title "..."`.

## This host (user environment)

WSL single-profile setup: one `default` profile, gateway running, a long-lived
`hermes serve --host 0.0.0.0 --port 9119` backend, and the dashboard as
`hermes dashboard --isolated --port 9120 --host 0.0.0.0` (basic-auth login,
creds in `.env`). Multi-agent orgs on a board need the persona profiles
CREATED FIRST — an assignee name with no matching profile strands its tasks
in `ready` (`skipped_nonspawnable` / stranded-in-ready diagnostics) and trips
the spawn-failure breaker. Windows browsers reach both at localhost; LAN
devices reach them at the Windows LAN IP (portproxy + firewall rules
`Hermes *` in place — see Remote access above). Windows Wi-Fi IP is DHCP —
if LAN access breaks, check it before blaming the portproxy.
