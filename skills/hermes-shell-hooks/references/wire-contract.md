# Shell hook wire contract (source-verified, v2026.9.24)

Verified by reading `agent/shell_hooks.py`, `hermes_cli/plugins.py`,
`agent/turn_context.py` in the local git install. Re-verify on version bump —
signatures below are implementation, not API.

## stdin JSON (all shell-hook events)

Built by `_serialize_payload` = `{"hook_event_name": event, **_payload_fields(kwargs)}`:

| key | value |
|---|---|
| `hook_event_name` | event that fired |
| `tool_name` | tool name (kwargs.tool_name; null for non-tool events) |
| `tool_input` | kwargs.args when it is a dict, else null |
| `session_id` | session id, falling back to `parent_session_id` |
| `cwd` | `Path.cwd()` at fire time |
| `profile` | active profile resolved at fire time (multiplex-aware) |
| `extra` | every other kwarg, stringified if unserializable |

`pre_llm_call` kwargs (from `_collect_pre_llm_call_context`): `session_id, task_id,
turn_id, user_message, conversation_history` (FULL message list), `is_first_turn,
model, platform, parent_session_id, sender_id` — all but session_id land in
`extra`. Payload can get big; parse with jq field-selectors only.

## matcher

- Only consulted for `pre_tool_call` / `post_tool_call`
  (`_TOOL_EVENTS`); on other events a `matcher:` is downgraded with a warning
  and the hook fires on every event of that type.
- `re.fullmatch` against tool_name. Leading/trailing whitespace stripped.
- Uncompilable regex → literal string equality fallback.
- No matcher → matches every tool (for tool events).

## stdout response grammar (`_parse_response`)

| event | parser | accepted stdout |
|---|---|---|
| `pre_tool_call` | `_parse_pre_tool_call` | Hermes `{"action":"block","message":...}` / `{"action":"modify","args":{...}}` / `{"action":"approve",...}`; Claude-Code dialect `{"decision":"block","reason":...}` also maps to block. `decision:"approve"` is deliberately NOT auto-allow (approve is reserved for the human-approval gate). |
| `pre_verify` | `_parse_pre_verify` | `{"action":"continue"|"block" (both = keep going), "message"|"reason": str}` — a nudge message; no message = no-op; anything else finishes the turn. |
| everything else | `_parse_context` | `{"context": str}` → returned as-is to the dispatcher. Consumed/injected for `pre_llm_call` (appended to the user message). Observers: emit nothing. |

Non-dict or non-JSON stdout → warning logged, `None` (no effect).

## Exit codes & failure semantics (`_evaluate_result`)

- exit **2** on a blocking-capable event (`_BLOCKING_EVENTS`, i.e. pre_tool_call /
  pre_verify) → hard block; block message = stdout JSON block message → stderr →
  default text.
- Spawn error / timeout → fail-open (`None`) unless `fail_closed: true` set **and**
  the event is blocking — then a canonical fail-closed block is returned.
- Other non-zero exits → warning; stdout still parsed.
- `fail_closed` on a non-blocking event is warned and ignored.
- timeout: per-entry `timeout` (default 60s, clamp 300s); the whole process group
  is killed (hooks run with `process_group=0`).

## Consent / allowlist

- Path: `~/.hermes/shell-hooks-allowlist.json` (`ALLOWLIST_FILENAME`), entries keyed
  by `(event, command)`; read-modify-write under flock.
- First fire per pair prompts; refusal = hook not registered that run
  (warning names the three escape hatches).
- Escape hatches (any one): CLI flag `--accept-hooks`, env
  `HERMES_ACCEPT_HOOKS=1`, config top-level `hooks_auto_accept: true`
  (`_resolve_effective_accept` reads the full config dict, so top level).
- `hermes hooks revoke <command>` removes matching allowlist entries (effective
  next restart); `hermes hooks doctor` checks exec bit, allowlist status, script
  mtime drift, stdout JSON validity, rough timing.

## Spawn environment

- `shlex.split` + `expanduser` of `command`, `shell=False`, `text=True` utf-8.
- Env = parent process env via `build_subprocess_env`; secrets scrubbed only when
  multiplex is active. In practice PATH = whichever surface launched the agent
  (desktop app ≠ login shell) — nvm/node tooling must be re-resolved in-script.
- `HERMES_HOME` follows the routed profile.
- Registration timing: `register_from_config` at CLI startup (`hermes_cli/main.py`)
  and gateway startup (`gateway/run.py`); Desktop/TUI/dashboard register when
  building the session's agent (that session's profile + consent allowlist).
  Python plugin hooks register BEFORE shell hooks, so a plugin pre_tool_call
  block wins ties.

## Injection consumption (`pre_llm_call`)

`agent/turn_context.py:_collect_pre_llm_call_context` runs once per turn, joins
all `{"context"}` contributions with blank lines, and appends the result to the
current user message (never the system prompt). Oversized pieces spill to disk
(`tools/hook_output_spill`) instead of inflating every later turn.

## VALID_HOOKS (excerpt)

`pre_tool_call, post_tool_call, transform_terminal_output, transform_tool_result,
transform_llm_output, pre_llm_call, post_llm_call, on_stream_start, on_stream_delta,
on_stream_end, on_interim_message, pre_verify, pre_api_request, post_api_request,
api_request_error, pre_auxiliary_call, post_auxiliary_call,
transform_api_error_classification` — plus `subagent_start/stop` and kanban
lifecycle events per docs; print the installed set via the excerpt above before
assuming an event name. Typos warn with a "did you mean" suggestion and skip.
