#!/usr/bin/env python3
"""引用ゲート: (1) [@key] と bib の整合 (2) DOI 解決+タイトル一致(Crossref)。
終了コード 0=通過 1=違反(未定義キー・DOI 404)。標準ライブラリのみ。
"""
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRICT = "--strict" in sys.argv
XREF_PREFIXES = ("fig-", "tbl-", "eq-", "sec-", "lst-", "thm-", "def-", "exm-")


def norm(s):
    s = unicodedata.normalize("NFKC", s).casefold()
    return set(re.findall(r"[a-z0-9]+|[\u3040-\u30ff\u4e00-\u9fff]+", s))


def fetch(doi):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    req = urllib.request.Request(
        url, headers={"User-Agent": "longform-check-refs/1.0 (mailto:check@example.org)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"status": e.code}
    except Exception as e:  # ネットワーク断等は警告扱い
        return {"status": "error", "msg": str(e)}


bib_path = ROOT / "refs" / "references.bib"
if not bib_path.exists():
    print("FAIL: refs/references.bib が無い")
    sys.exit(1)
bib_text = bib_path.read_text(encoding="utf-8")
entries = {}
for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@|\Z)", bib_text, re.S):
    key, body = m.group(1).strip(), m.group(2)
    dm = re.search(r"^\s*doi\s*=\s*[{\"]([^{}\"]+)[}\"]", body, re.I | re.M)
    tm = re.search(r"^\s*title\s*=\s*[{\"]([^{}\"]+)[}\"]\s*,?\s*$", body, re.I | re.M)
    entries[key] = {
        "doi": dm.group(1).strip() if dm else None,
        "title": re.sub(r"\\", "", tm.group(1)).strip() if tm else None,
    }

files = sorted((ROOT / "manuscript").glob("**/*.md"))
cited = set()
for f in files:
    for k in re.findall(r"(?<![\w@.\-])@([A-Za-z][\w:.\-]*)", f.read_text(encoding="utf-8")):
        if not k.startswith(XREF_PREFIXES):
            cited.add(k)

errors, warns = [], []
missing = sorted(cited - set(entries))
if missing:
    errors.append(f"未定義キー(bibに存在しない): {missing}")
uncited = sorted(set(entries) - cited)
if uncited:
    warns.append(f"未引用エントリ: {uncited}")

for key, e in entries.items():
    if not e["doi"]:
        warns.append(f"{key}: DOI なし → 実在確認(layer2)スキップ")
        continue
    r = fetch(e["doi"])
    if r.get("status") == 404:
        errors.append(f"{key}: DOI が実在しない {e['doi']}")
    elif r.get("status") == "error":
        warns.append(f"{key}: Crossref 到達失敗 {r.get('msg')}")
    else:
        title = (r.get("message", {}).get("title") or [""])[0]
        a, b = norm(e["title"] or ""), norm(title)
        j = len(a & b) / max(1, len(a | b))
        if j < 0.5:
            msg = f"{key}: タイトル不一致(jaccard={j:.2f}) bib=『{e['title']}』 vs Crossref=『{title}』"
            (errors if STRICT else warns).append(msg)
        else:
            print(f"OK  {key}  DOI解決+タイトル一致(jaccard={j:.2f})")

print("\n--- 結果 ---")
for w in warns:
    print("WARN:", w)
for e in errors:
    print("FAIL:", e)
print(f"entries={len(entries)} cited={len(cited)} files={len(files)}")
if errors:
    sys.exit(1)
print("check-refs: PASS")
