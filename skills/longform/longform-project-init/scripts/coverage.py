#!/usr/bin/env python3
"""カバレッジ・整合ゲート: 承認済み outline(YAML) vs manuscript。
- セクションファイル存在 / claim の refs がその節で引用されているか
- 文字数予算(下限50%未満でFAIL・上限180%超でWARN)
- glossary 禁止表記スキャン。標準ライブラリのみ(yaml不要の専用パーサ)。

outline スキーマのインデント規約:
  0=最上位キー/sections:  2='- '節項目  4=節フィールド  6='- 'claim項目/完了条件  8=claimフィールド(refs)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LO, HI = 0.5, 1.8
XREF = ("fig-", "tbl-", "eq-", "sec-", "lst-", "thm-", "def-", "exm-")


def scalar(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip('"') for x in v[1:-1].split(",") if x.strip()]
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if re.fullmatch(r"\d+", v):
        return int(v)
    return v


def parse_outline(yaml_text):
    data, sections, cur, cur_list = {}, None, None, None
    for raw in yaml_text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0:
            k, _, v = line.partition(":")
            if k.strip() == "sections":
                sections = data["sections"] = []
                cur, cur_list = None, None
            else:
                data[k.strip()] = scalar(v)
            cur_list = None
        elif indent == 2 and line.startswith("- "):
            cur = {"claims": [], "done_criteria": []}
            sections.append(cur)
            k, _, v = line[2:].partition(":")
            cur[k.strip()] = scalar(v.strip())
            cur_list = None
        elif indent == 4 and cur is not None:
            k, _, v = line.partition(":")
            k = k.strip()
            if k in ("claims", "done_criteria"):
                cur_list = k
            else:
                cur[k] = scalar(v)
        elif indent == 6 and cur is not None:
            if line.startswith("- "):
                if cur_list == "claims":
                    item = {}
                    k, _, v = line[2:].partition(":")
                    item[k.strip()] = scalar(v.strip())
                    cur["claims"].append(item)
                elif cur_list == "done_criteria":
                    cur["done_criteria"].append(scalar(line[2:]))
            else:
                k, _, v = line.partition(":")
                if cur_list == "claims" and cur["claims"]:
                    cur["claims"][-1][k.strip()] = scalar(v)
        elif indent >= 8 and cur is not None and cur_list == "claims" and cur["claims"]:
            k, _, v = line.partition(":")
            cur["claims"][-1][k.strip()] = scalar(v)
    return data


def fail(msgs):
    for m in msgs:
        print("FAIL:", m)
    print("coverage: FAIL")
    sys.exit(1)


outline_path = ROOT / "spec" / "outline.md"
if not outline_path.exists():
    fail(["spec/outline.md が無い(longform-outline を先に実行)"])
otext = outline_path.read_text(encoding="utf-8")
m = re.search(r"```yaml\n(.*?)\n```", otext, re.S)
if not m:
    fail(["outline.md に ```yaml ブロックが無い(スキーマ: longform-outline SKILL.md)"])
try:
    spec = parse_outline(m.group(1))
except Exception as e:
    fail([f"outline パース失敗: {e}"])
sections = spec.get("sections") or []
if not sections:
    fail(["outline の sections が空"])


def cited_keys(path):
    t = path.read_text(encoding="utf-8")
    return set(
        k
        for k in re.findall(r"(?<![\w@.\-])@([A-Za-z][\w:.\-]*)", t)
        if not k.startswith(XREF)
    )


probs, warns = [], []
print("--- section report ---")
for s in sections:
    f = ROOT / "manuscript" / s.get("file", "")
    if not f.exists():
        probs.append(f"{s.get('id')}: 原稿ファイル無し {s.get('file')}")
        continue
    t = f.read_text(encoding="utf-8")
    body = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    body = re.sub(r"\[@[^\]]+\]", "", body)
    body = re.sub(r"[*_`]", "", body)
    body = re.sub(r"\{#[^}]+\}", "", body)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    chars = len(re.sub(r"\s", "", body))
    if chars == 0:
        print(f"{s.get('id')}: 未起草(skip)")
        continue
    budget = s.get("word_budget") or 0
    if budget:
        if chars < budget * LO:
            probs.append(f"{s.get('id')}: 文字数不足 {chars}/{budget}")
        elif chars > budget * HI:
            warns.append(f"{s.get('id')}: 文字数超過 {chars}/{budget}")
    keys = cited_keys(f)
    for c in s.get("claims") or []:
        for ref in c.get("refs") or []:
            if ref not in keys:
                probs.append(
                    f"{s.get('id')}: claim『{str(c.get('claim'))[:24]}…』の根拠 {ref} がこの節で未引用"
                )
    print(f"{s.get('id')}: {chars}字 (予算{budget}) refs={sorted(keys)}")

    gl = ROOT / "spec" / "glossary.md"
    if gl.exists():
        for line in gl.read_text(encoding="utf-8").splitlines():
            m2 = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
            if not m2:
                continue
            term, bad = m2.group(1).strip(), m2.group(2).strip()
            if not term or set(term) <= set("-: ") or term in ("正用語", "正"):
                continue
            for b in [x.strip() for x in bad.split(",") if x.strip() and x.strip() != "—"]:
                if b in t:
                    probs.append(f"glossary違反: {f.name} に禁止表記『{b}』(正『{term}』)")

if spec.get("approved") is not True:
    warns.append("outline が未承認(approved: false) — 起草前ゲート①が未通過")

print("--- 結果 ---")
for w in warns:
    print("WARN:", w)
for p in probs:
    print("FAIL:", p)
if probs:
    sys.exit(1)
print("coverage: PASS")
