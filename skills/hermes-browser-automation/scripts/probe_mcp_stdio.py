#!/usr/bin/env python3
"""End-to-end probe for the WSL -> Windows chrome-devtools-mcp bridge.

Speaks newline-delimited MCP JSON-RPC over stdio to chrome-devtools-mcp spawned
through Windows interop (cmd.exe / npx). Verifies the whole chain before handing
the "reload the session" step to the user:

    initialize -> notifications/initialized -> tools/list -> new_page
    -> list_pages -> take_screenshot -> clean shutdown (stdin close)

Exit 0 plus a final "PROBE_OK" line means verified; the page screenshot is
written to --out. Any failing step prints PROBE_FAIL plus the server's stderr
tail and exits 1.

Usage (run from WSL with python3):
  python3 probe_mcp_stdio.py                      # Mode A: dedicated visible Chrome window
  python3 probe_mcp_stdio.py --autoConnect        # Mode B: attach to the running real Chrome;
                                                  #   the user must approve the remote-debugging
                                                  #   dialog on the Windows side
  python3 probe_mcp_stdio.py --hold 25            # keep the window up N seconds for a watcher
  python3 probe_mcp_stdio.py --url https://example.com --out /tmp/probe.png

Requires: WSL interop (cmd.exe), Node/npx on the Windows side, Google Chrome.
Verified against chrome-devtools-mcp 1.10.1 (30 tools).
"""

import argparse
import base64
import json
import subprocess
import sys
import threading
import time

INTEROP_CMD = ["/mnt/c/Windows/System32/cmd.exe", "/c", "npx", "-y",
               "chrome-devtools-mcp@latest"]
CWD = "/mnt/c/Users"  # real Windows path mapping: avoids the UNC cwd-fallback noise


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--autoConnect", action="store_true",
                    help="Mode B: attach to the running real Chrome instead of "
                         "launching a dedicated one")
    ap.add_argument("--url", default="https://example.com",
                    help="page to open for the navigation/screenshot check")
    ap.add_argument("--out", default="probe_mcp_stdio.png",
                    help="where to write the screenshot PNG")
    ap.add_argument("--hold", type=int, default=0, metavar="SEC",
                    help="seconds to keep the browser open before shutdown, "
                         "so a watcher can see it")
    ap.add_argument("--init-timeout", type=int, default=150,
                    help="initialize timeout (first npx run downloads the package)")
    ap.add_argument("--page-timeout", type=int, default=240,
                    help="new_page timeout (Mode B waits for the user approval dialog)")
    args = ap.parse_args()

    mcp_flags = ["--no-usage-statistics"]
    if args.autoConnect:
        mcp_flags.append("--autoConnect")
    proc = subprocess.Popen(INTEROP_CMD + mcp_flags, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, bufsize=1, cwd=CWD)
    stdin, stdout, stderr = proc.stdin, proc.stdout, proc.stderr
    assert stdin and stdout and stderr  # all three pipes are requested above

    responses = {}          # request id -> response message
    stderr_tail = []
    lock = threading.Lock()

    def reader() -> None:
        for line in stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            with lock:
                if isinstance(msg.get("id"), int):
                    responses[msg["id"]] = msg

    def errdrain() -> None:
        for line in stderr:
            stderr_tail.append(line.rstrip())

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=errdrain, daemon=True).start()

    next_id = 0

    def call(method, params, timeout):
        nonlocal next_id
        next_id += 1
        rid = next_id
        stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid,
                                "method": method, "params": params}) + "\n")
        stdin.flush()
        deadline = time.time() + timeout
        while time.time() < deadline:
            with lock:
                if rid in responses:
                    return responses[rid]
            time.sleep(0.25)
        return None

    def result_text(resp):
        try:
            return "".join(c.get("text", "") for c in resp["result"]["content"]
                           if c.get("type") == "text")
        except (KeyError, TypeError):
            return ""

    def fail(msg):
        print("PROBE_FAIL:", msg)
        if stderr_tail:
            print("stderr tail:\n" + "\n".join(stderr_tail[-15:]))
        try:
            stdin.close()
        except Exception:
            pass
        return 1

    r = call("initialize",
             {"protocolVersion": "2025-06-18", "capabilities": {},
              "clientInfo": {"name": "hermes-probe", "version": "1.0"}},
             timeout=args.init_timeout)
    if r is None or "result" not in r:
        return fail("initialize failed (server never answered)")
    print("initialize OK:", json.dumps(r["result"].get("serverInfo", {})))

    stdin.write(json.dumps({"jsonrpc": "2.0",
                            "method": "notifications/initialized"}) + "\n")
    stdin.flush()

    r = call("tools/list", {}, timeout=60)
    if r is None or "result" not in r:
        return fail("tools/list failed")
    print("tools/list OK:", len(r["result"]["tools"]), "tools")

    waiting = (" waiting for the user approval dialog on the real Chrome"
               if args.autoConnect else "")
    print(f"calling new_page({args.url}) ...{waiting}", flush=True)
    r = call("tools/call", {"name": "new_page", "arguments": {"url": args.url}},
             timeout=args.page_timeout)
    txt = result_text(r) if r else ""
    if r is None or "result" not in r or "Could not connect" in txt:
        return fail("new_page failed / could not connect: " + (txt or "no response")[:300])
    print("new_page result:", txt[:400])

    r = call("tools/call", {"name": "list_pages", "arguments": {}}, timeout=60)
    txt = result_text(r) if r else ""
    print("list_pages:", txt[:400])
    page_id = None
    for line in txt.splitlines():
        s = line.strip()
        if args.url in s:
            digits = ""
            for ch in s:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            if digits:
                page_id = int(digits)
                break
    if page_id is None:
        return fail("could not determine pageId from list_pages")

    r = call("tools/call",
             {"name": "take_screenshot", "arguments": {"pageId": page_id}},
             timeout=90)
    img_b64 = None
    if r and "result" in r:
        for c in r["result"].get("content", []):
            if c.get("type") == "image":
                img_b64 = c.get("data")
    if not img_b64:
        return fail("no image returned by take_screenshot")
    with open(args.out, "wb") as f:
        f.write(base64.b64decode(img_b64))
    print("SCREENSHOT_SAVED:", args.out)

    if args.hold > 0:
        print(f"holding {args.hold}s for observation ...", flush=True)
        time.sleep(args.hold)

    try:
        stdin.close()
    except Exception:
        pass
    try:
        rc = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        rc = proc.wait()
    print("probe server exited rc=", rc)
    print("PROBE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
