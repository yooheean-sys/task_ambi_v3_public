---
name: hermes-browser-automation
description: "Use when setting up or driving Hermes browser automation."
version: 1.0.0
license: MIT
author: Hermes Agent
metadata:
  hermes:
    tags: [hermes, browser, browser-use, wsl, chrome, mcp]
---

# Hermes Browser Automation

How to give Hermes browser control and point it at the right browser: the default Browser Use mode, backend selection, and the WSL→Windows Chrome MCP bridge. Full WSL→Windows recipe: `references/wsl-windows-browser.md`.

## When to Use

- The user asks what browser capabilities Hermes has, or wants to try/operate a browser through Hermes.
- Choosing among browser backends (default Browser Use mode, cloud providers, CDP, MCP bridge) — especially "Hermes runs in WSL but must drive the Windows-side browser".
- Setting up, testing, or switching the chrome-devtools-mcp bridge, or diagnosing browser tools that error instead of opening a window.

## Hard rules

- Default Browser Use mode (`browser_exec`) drives Hermes' packaged headless Chromium INSIDE WSL; it never touches the user's Windows Chrome/Edge. State this before any demo or the user watches the wrong screen.
- This user watches agent-driven browsing live on their desktop. Prefer a visible (headful) browser and announce what will appear on screen before driving it; never add `--headless` unless asked.
- Demo on a target where the operations are visible: static pages (example.com) show no per-operation change, so a watching user can verify nothing. Drive an interactive page instead — e.g. the Wikipedia portal (type in the search box, click Search, watch the navigation) — and announce the operation sequence with tool names first.
- Cleaning up a stuck bridge browser: never kill `chrome.exe` by image name — that also kills the user's real browser. Kill only processes whose CommandLine matches the chrome-devtools-mcp profile path (PowerShell `Get-CimInstance` filter; inside bash double quotes escape `$_` as `\$_` or the filter silently breaks).
- To control the user's real Windows browser from WSL Hermes, use the chrome-devtools-mcp MCP bridge — never `/browser connect`. `/browser connect` is an interactive CLI-only slash command (never dispatched in desktop/gateway sessions), and under WSL NAT it cannot reach Windows Chrome's CDP port, which binds to 127.0.0.1.
- chrome-devtools-mcp `--autoConnect` has no fallback: if the real Chrome is not running with remote debugging enabled (`chrome://inspect/#remote-debugging`, Chrome 144+), every browser tool errors instead of launching a browser. For "just show me a browser" setups use the default launch mode (dedicated persistent profile, headful window).
- `hermes mcp add` is discovery-first and interactive — it ends with "Enable all N tools? [Y/n/select]". Pipe `echo Y |` or it cancels after discovery.
- After `hermes mcp add`, only the user can load the tools into a live session (`/reload-mcp` or a new session) — hand that step to them explicitly.
- Mid-session config switch does NOT reach an already-spawned MCP server process: if autoConnect was registered after this session started, the session's server still runs the old args and opens a dedicated-profile Chrome. Detect via PowerShell chrome.exe CommandLine containing the chrome-devtools-mcp profile path; kill only those processes, then the user must open a new chat for the new mode to take effect. Desktop app: the slash palette has NO `/reload-mcp` (typing it just returns a notice pointing at the CLI), so the refresh there is a new chat; the gateway meanwhile connects the new server from config within ~1 min (see `~/.hermes/logs/mcp-stderr.log`).
- Verify feature claims against the live docs: `curl -s https://hermes-agent.nousresearch.com/docs/llms.txt` is the full feature index; `llms-full.txt` is the whole doc set in one grep/sed-able file. web_extract on docs pages can die on a keyless-Firecrawl 403 — curl+grep is the reliable path.

## Backend selection

| Goal | Path |
|---|---|
| Try/demo browser features, zero setup | Default Browser Use mode (`browser_exec`, packaged WSL Chromium) |
| User's own logged-in browser, same OS | `/browser connect` (CLI sessions) or `browser.cdp_url` in config.yaml |
| WSL Hermes → Windows browser, visible | chrome-devtools-mcp MCP bridge → `references/wsl-windows-browser.md` |
| Anti-bot/CAPTCHA/scraping at scale | Cloud provider (Browser Use Cloud / Browserbase / Firecrawl) via `hermes tools` → Browser Automation; credentials in `~/.hermes/.env` (e.g. `BROWSER_USE_API_KEY`), selection stored as `browser.cloud_provider` |

## First demo of Browser Use mode

1. One `browser_exec` call: `new_tab(url)` → `wait_for_load()` → `page_info()` / `js("document.title")` → `capture_screenshot()`. Batch navigate+extract into a single call; don't spend one call per action.
2. Report what came back and note the browser ran headless inside WSL.

## Driving the bridge once its tools are loaded

The `mcp__chrome_devtools_win__*` tools arrive deferred: `tool_describe` the needed schemas first, then `tool_call` them. Core loop — pageId from `new_page`'s page list, uids from `take_snapshot`, act with `fill`/`click`, verify with `take_screenshot`: `references/chrome-devtools-driving.md`.

## Changing the registered bridge

To change chrome-devtools-mcp flags (e.g. switch to real-profile attach later): `hermes mcp remove chrome-devtools-win`, then re-add with the new args, then the user refreshes the session (CLI: `/reload-mcp`; desktop app: new chat).

## Verify without waiting for a session reload

Before handing the reload step over, the whole chain can be verified agent-side by speaking MCP JSON-RPC over stdio directly to the server (initialize → notifications/initialized → tools/call) — it launches the real Chrome on Windows, navigates, screenshots, and cleans up on stdin close. Ready-made script: `python3 scripts/probe_mcp_stdio.py` from the skill's directory (`--autoConnect` for Mode B, `--hold N` keeps the window up for a watcher; exit 0 = verified). Full recipe: `references/wsl-windows-browser.md`.

## User handout

After completing a browser setup for this user, also write a human-executable markdown handout in `~/` (Japanese; title free of Obsidian-forbidden chars; no `<placeholder>` path notation — Obsidian mangles angle-bracket paths). The handout for the chrome-devtools bridge lives at `~/hermes_windows_chrome_mcp_setup.md` — update it rather than writing a new one.
