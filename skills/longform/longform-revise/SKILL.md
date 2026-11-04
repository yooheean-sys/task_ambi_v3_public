---
name: longform-revise
author: Hermes Agent
license: MIT
description: "Use when applying review feedback to a manuscript by patch."
version: 1.0.0
metadata:
  hermes:
    tags: [writing, review]
    parent: longform-writing-pipeline
---

# longform-revise(レビュー反映 — patch 専用)

指摘は targeted patch で適用する。節の再生成は diff を壊すので禁止。

## When to Use
- 人間レビュー・ゲート②通読の指摘を原稿へ反映するとき
- 査読コメント対応(返信状自体は別物。本 skill は原稿修正のみ)

## 手順
1. **指摘を整理する**: 節・箇所・種別(表現/事実/構成)の一覧にする。1文1行のおかげで行単位で特定できる。
2. **1指摘1patch で適用する**: patch ツールで置換する。構成変更が必要な指摘は outline 修正として human 承認を先に取る(勝手に outline を変えない)。
3. **影響セクションのゲートを回す**: `just lint` / `check-refs` / `coverage` / `build-html`。
4. **差分を提示する**: `just diff`(pandiff 未導入なら git diff)。報告して完了。

## Pitfalls
- 全文再生成は禁止。小さい patch を積む。
- 指摘が outline の claim と矛盾する場合は outline 側を直す提案として止まる。
- docx→markdown 変換は禁止(トラック変更が無条件承認される危険)。
