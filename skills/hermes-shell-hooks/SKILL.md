---
name: hermes-shell-hooks
description: "Use when creating or debugging Hermes shell hooks."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, hooks, shell-hooks, configuration]
    related_skills: [hermes-agent]
---

# Hermes Shell Hooks (authoring & debugging)

Scope: shell-script hooks declared in the **profile** `config.yaml` (`hooks:` block),
scripts living under `~/.hermes/agent-hooks/` by convention. Covers the
check/surface pair pattern (validate a file right after the agent edits it, then
inject the verdict into the next model turn as an auto-fix loop). Out of scope:
gateway hooks (`HOOK.yaml`/`handler.py`, gateway-only) and Python plugin hooks
(`ctx.register_hook()`).

## When to Use

- Creating a hook that reacts to the agent's tool calls — validate after edit,
  auto-format, context injection, guardrails.
- A hook script/stdout response is not firing, not injecting context, or being
  skipped by consent; registering, testing (`hermes hooks list/test/doctor`),
  or debugging an existing shell hook.
- Building a "check the artifact after the agent writes it, and make the agent
  fix it if broken" loop for any file type (here: mermaid render-validity).

## Always-on rules

- **Confirm the wire contract in the installed source before writing a hook.**
  Read `~/.hermes/hermes-agent/agent/shell_hooks.py` (payload, response parsing,
  consent) and `~/.hermes/hermes-agent/hermes_cli/plugins.py` (`VALID_HOOKS`).
  The docs are ambiguous on details — e.g. `hooks_auto_accept` sits at
  **top level** of config.yaml, not inside `hooks:`; nested there it is parsed
  as an unknown event (warning + skipped).
- **matcher is honored only for pre_tool_call/post_tool_call** and is a
  *fullmatch* regex on tool_name (`write_file|patch` matches both, nothing
  else fires). It is stripped of YAML folding whitespace; an invalid regex
  falls back to literal equality.
- **Observers print nothing.** Only a `pre_llm_call` hook's `{"context": "..."}`
  stdout JSON is consumed and appended to the user message (never the system
  prompt). For post_tool_call and other observer events, emit no stdout.
- **Hook scripts run with the launching surface's env; nvm-managed CLIs are
  usually NOT on that PATH.** Resolve the binary inside the script
  (`command -v`, else glob `$HOME/.nvm/versions/node/*/bin/<tool>`) and prepend
  its dir to PATH — a `#!/usr/bin/env node` entry point dies with
  `/usr/bin/env: 'node': No such file or directory` otherwise. Prove it with a
  minimal-env mimic: `env -i HOME=<home> PATH=/usr/bin:/bin <cmd>`.
- **Hooks register at agent build, not live.** CLI/gateway startup or the
  Desktop/TUI/dashboard agent build loads them; the session that existed before
  registration does not pick the hook up. Verify by firing a matching edit and
  reading the hook's own state/log files on disk, not by assuming.
- **Consent gate:** the first fire of each `(event, command)` pair prompts the
  user; non-TTY runs (`hermes chat -q` children, cron) silently skip unless one
  of `--accept-hooks`, `HERMES_ACCEPT_HOOKS=1`, or top-level
  `hooks_auto_accept: true` is set. If a tool command returns BLOCKED
  (exit -1, "user has NOT consented — do not retry"), stop, summarize state and
  the next step, and wait. Never rephrase or retry around it.
- Terminal-command edits (`sed`, heredoc redirection) bypass hooks entirely —
  hooks only see tool calls. State this limitation when the hook matters.

## Procedure

1. **Contract check (cheap, first).**
   ```bash
   grep -n 'tool_input\|_parse_response\|def register_from_config' \
     ~/.hermes/hermes-agent/agent/shell_hooks.py
   awk '/VALID_HOOKS/{p=1; n=0} p{print; n++; if(n>30) exit}' \
     ~/.hermes/hermes-agent/hermes_cli/plugins.py
   ```
   Decision: log/verify *after* the fact → `post_tool_call`; make the *next*
   model turn aware (auto-fix loop) → add `pre_llm_call` surface; prevent the
   call outright → `pre_tool_call` with block/modify directive.
2. **Write one script with subcommands** under `~/.hermes/agent-hooks/<name>.sh`
   (`check` / `surface` args), `chmod +x` it. Build JSON only with `jq`; keep a
   non-matching run a no-op (exit 0, no stdout, no state file writes) so it is
   safe at high frequency. Injected context: Japanese (user expects Japanese
   responses), line-bounded (≤ ~14 lines) — multibyte-safe truncation by
   `head -14`, not byte-count `head -c`.
3. **Unit-test before registering.** Hand-build a payload JSON and pipe it in:
   `printf '{"hook_event_name":"post_tool_call","tool_name":"write_file",...}' | script.sh check`,
   then inspect the state/log files. Gotcha: the `pre_llm_call` stdin payload
   carries the **full conversation history** under `extra` — read only needed
   fields with `jq`, never dump the payload into logs (secret-sensitive).
4. **Register via `hermes config set` — never hand-edit config.yaml.**
   ```bash
   hermes config set 'hooks.post_tool_call' '- matcher: "write_file|patch"
     command: "~/.hermes/agent-hooks/mermaid-check.sh check"
     timeout: 120'
   ```
   config set auto-coerces quoted YAML/JSON list literals into real lists; use
   `--force` only if the path is refused as unknown. `timeout` defaults 60,
   clamped to 300. Leave `hooks_auto_accept: false` unless the user opts in —
   it is a global bypass, not per-hook.
5. **Verify the registration and the real path.**
   `hermes hooks list` (matcher/timeout/consent), `hermes hooks doctor`
   (exec bit, mtime drift, JSON validity — rerun after every script edit),
   `hermes hooks test post_tool_call --for-tool write_file --payload-file P.json`
   and a `pre_llm_call` test. `hooks test` shares the production evaluator, so
   its printed response is exactly what the agent consumes.
6. **Live end-to-end in a fresh session.** Have the session edit a target file
   in a scratch dir, then watch `state.jsonl`/`log.jsonl` and the session
   transcript for the injected context block. Confirm the NG→fix→re-check
   cycle actually repeats (the surface hook only fires once per consumed
   batch).

## Support files

- `references/wire-contract.md` — per-event stdin fields, matcher semantics,
  response grammars (directives/exit codes), consent allowlist, spawn env.
- `templates/mermaid-check.sh` — a working check/surface pair (mermaid
  render-validation with sha256 cache); copy and swap the checker.
