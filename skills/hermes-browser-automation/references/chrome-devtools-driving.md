# Driving the chrome-devtools-mcp bridge in-session (mcp__chrome_devtools_win__*)

Once the bridge's tools are loaded into a session they arrive DEFERRED: present in the tool catalog but not callable until their schemas are loaded. Registration, modes, and transport pitfalls live in `wsl-windows-browser.md`.

## Tool loading

1. `tool_describe` the batch of schemas you need up front (new_page, take_snapshot, fill, click, navigate_page, take_screenshot, press_key, evaluate_script, list_pages) — one call for the batch, not one call per tool.
2. Invoke via `tool_call`. Sequentialize only calls whose output the next call needs; batch the rest.

## Core loop (each step's output feeds the next)

1. `new_page(url)` → the result echoes the page list; the target page's number IS its pageId. Keep that pageId for every later call (pageId numbering rule: `wsl-windows-browser.md` pitfalls).
2. `take_snapshot(pageId)` → a11y tree with `uid=N_M` per element; use uids from the latest snapshot only. Snapshot output is often huge (every `<option>` enumerated line-by-line) and anything over ~50KB spills to a spillover file — when it does, grep/read that local file with `execute_code` for the uid you need instead of re-calling `take_snapshot`; never echo the snapshot back to the user wholesale.
3. Act: `fill(pageId, uid, value)` for inputs/textareas/selects; `click(pageId, uid)` (clicks can trigger the navigation); `press_key(pageId, key)` for shortcuts/Enter. If `fill` errors with "did not become interactive" or simply hangs on an element the snapshot marks `focused` (collapsing search comboboxes behave this way), do NOT retry `fill` — the element already has focus and will never satisfy fill's interactivity wait. Fallback: focus it (click or press_key Tab), `type_text` into it, then `press_key` Enter to submit; Enter BEFORE any text is typed submits an empty query and navigates, so type first.
4. Re-orient or move: `navigate_page(pageId, type=url|back|forward|reload, url=…)`; `reload` accepts `ignoreCache: true`.
5. Verify visually: `take_screenshot(pageId)` returns a `MEDIA:` image path — embed it in the reply (`![alt](MEDIA:<path>)`) and inspect it yourself before claiming the page state.

## Live-viewed demo rules

- Pick a target where the operations are visible. Static pages (example.com) show no per-operation change, so a watching user can verify nothing. Interactive default that works: the Wikipedia portal (one search box + Search button → article navigation); any site with a form works too. The live-view proof is the user reading the typed query string on screen — a query with zero hits still demonstrates it (suggest/correction UI reacts visibly), so the term need not succeed.
- Announce the operation sequence up front with tool names (navigate → snapshot → fill → click → screenshot), then report each completed step, so the user can map on-screen changes to what the agent ran.
