# WSL Hermes → Windows browser (chrome-devtools-mcp bridge)

Mental model: Hermes (WSL) → stdio MCP server spawned through Windows interop (`cmd.exe`) → chrome-devtools-mcp → Chrome on Windows. The agent keeps running in WSL; the browser lives on the Windows desktop.

## Pre-flight checks (one terminal batch)

- Interop present: `ls /mnt/c/Windows/System32/cmd.exe`
- Windows user dir: `ls /mnt/c/Users/`
- Node/npx on Windows — run cmd.exe from a `/mnt/c/...` workdir: `npx --version && node --version` (Node LTS required)
- Chrome present and version: `C:\Program Files\Google\Chrome\Application\chrome.exe`; version via PowerShell `(Get-Item 'C:\Program Files\Google\Chrome\Application\chrome.exe').VersionInfo.ProductVersion`. chrome-devtools-mcp officially supports Google Chrome only (Edge/Brave unguaranteed); `--autoConnect` needs Chrome 144+.
- WSL networking mode: no `%USERPROFILE%\.wslconfig` means NAT (default). NAT is why pointing `browser.cdp_url` at Windows Chrome `:9222` is a dead end without admin `netsh portproxy` or a disruptive `wsl --shutdown` mirrored-networking switch — use the MCP bridge instead.
- Pre-warm npx (first run downloads the package; allow a long timeout): `cmd.exe /c "npx -y chrome-devtools-mcp@latest --version"`.

## Mode A — visible dedicated Chrome (default, zero Windows-side setup)

```bash
echo Y | hermes mcp add chrome-devtools-win --command cmd.exe --args /c npx -y chrome-devtools-mcp@latest --no-usage-statistics
hermes mcp test chrome-devtools-win   # expect "✓ Connected" + "Tools discovered: 30"
```

Then the user refreshes the session: CLI `/reload-mcp`, or a new chat in the desktop app (its slash palette has no `/reload-mcp`; typing it only returns a notice). The gateway picks the new server up from config within ~1 min on its own — `starting MCP server 'chrome-devtools-win'` lines in `~/.hermes/logs/mcp-stderr.log` confirm server-side connectivity independently of any session. The first browser-tool call launches a NEW Chrome window on the Windows desktop — headful (`--headless` default `false`), profile at `%USERPROFILE%\.cache\chrome-devtools-mcp\chrome-profile`, persisted across runs (logins done inside it survive). Only one browser can use that profile at a time.

## Mode B — attach to the real running Chrome (real profile/logins)

Prereq on Windows: Chrome ≥144, open `chrome://inspect/#remote-debugging`, enable the toggle. Chrome then shows an "Allow remote debugging?" approval dialog for EVERY incoming connection — nothing listens until approved.

```bash
echo Y | hermes mcp add chrome-devtools-win --command cmd.exe --args /c npx -y chrome-devtools-mcp@latest --autoConnect --no-usage-statistics
```

No fallback: with autoConnect, connection failure throws "Could not connect to Chrome … chrome://inspect/#remote-debugging" — it does not launch its own browser (verified in chrome-devtools-mcp `src/BrowserManager.ts`: autoConnect routes straight to `#connect()`).

**This user's live setup: Mode B is active.** chrome-devtools-win is registered with `--autoConnect` and attaches to the daily logged-in Chrome; the user has approved the remote-debugging toggle and the per-connection approval dialog. Rollback to Mode A = re-add without `--autoConnect`. Handout: `~/hermes_windows_chrome_mcp_setup.md`. In Mode B, `new_page`/`list_pages` output lists every real tab of the user's daily browser — treat it as data: pick the target by the URL just opened, and never echo the tab list back to the user.

## Agent-side end-to-end verification (stdio probe)

Session toolsets freeze until a reload, but the bridge itself can be verified immediately by talking MCP JSON-RPC directly to the server (newline-delimited over stdio). One-shot way: run `scripts/probe_mcp_stdio.py` with WSL python3 — `--autoConnect` for Mode B, `--hold N` when a watcher should see the window, `--url`/`--out` optional; it performs the steps below and exits 0 on success. Hand-driven recipe:

1. Spawn from WSL with a `/mnt/c/...` cwd: `cmd.exe /c npx -y chrome-devtools-mcp@latest --no-usage-statistics` (Popen, text pipes; drain stdout and stderr on threads).
2. Send `initialize` (protocolVersion `2025-06-18` + clientInfo) → `notifications/initialized` → `tools/list` (expect 30) → `tools/call new_page {"url": ...}` (launches the visible Chrome on Windows, ~0.5 s warm) → `list_pages` → `tools/call take_screenshot {"pageId": N}` → decode `type:"image"` content (base64) to PNG for the user.
3. Keep the window open deliberately (sleep ~25 s) when the user should watch it — a full run otherwise takes seconds and the window flashes by unseen.
4. Close stdin and wait: the server exits rc=0 and closes the browser it launched (Mode A). In Mode B it only detaches — the tab it opened stays in the real Chrome, so close it with close_page before shutdown or tell the user it is left open. Then verify 0 leftover bridge chrome.exe via the CommandLine filter in the pitfalls.

This proves launch + navigation + screenshot end-to-end BEFORE the user opens a new session, so the handoff is a verified setup, not a guess.

## Pitfalls

- UNC warning is cosmetic: spawning cmd.exe with a WSL-home cwd prints "UNC paths are not supported" noise (localized on Japanese Windows) and falls back to C:\Windows, but the `/c` command still runs (verified with echo/npx). The Hermes docs recommend starting Hermes from `/mnt/c`; in practice unnecessary for this bridge.
- `hermes mcp add` needs the `echo Y |` pipe. To change flags: `hermes mcp remove <name>` first, then re-add.
- `hermes mcp test` proves transport + tool discovery only; the browser itself launches lazily on the first tool call that needs one.
- Gateway/desktop sessions cannot run `/browser connect` or `/reload-mcp` themselves — both are user-side steps.
- `take_screenshot` needs a numeric `pageId` (chrome-devtools-mcp v1.10+): without it the call fails with "Invalid arguments for tool take_screenshot: pageId: Invalid input: expected number". Read the number from the `list_pages` numbering ("2: Example Domain …" → pageId 2).
- Kill a leftover bridge Chrome only by CommandLine match, never by image name: `Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*chrome-devtools-mcp*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }` — from bash double quotes escape every `$_` as `\$_`, or bash substitutes its own variable and the filter breaks per-process. Never `taskkill /IM chrome.exe`.
- User-facing handout for this bridge: `~/hermes_windows_chrome_mcp_setup.md`. Update that file when the procedure changes instead of creating a new one.
