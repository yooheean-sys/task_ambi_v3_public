---
name: longform-outline
author: Hermes Agent
license: MIT
description: "Use when creating the outline spec set before drafting."
version: 1.0.0
metadata:
  hermes:
    tags: [writing, outline, spec]
    parent: longform-writing-pipeline
---

# longform-outline(仕様層の生成と承認ゲート①)

承認前の執筆を禁止するゲートを持つ。outline.md は人間承認の対象であると同時に、scripts/coverage.py が機械パースする対象でもある(```yaml ブロック固定スキーマ)。

## When to Use
- project-init 直後に目次と内容方針を固めるとき
- 既存 repo に仕様層が無いとき

## 入力
- トピック・目的・読者・文書種別・分量目標
- ソース(vault ノート・PDF・既知文献)

## 手順
1. **ソースを収集し引用候補を実在確認する**: DOI は Crossref(`api.crossref.org/works/<doi>`)、タイトル検索は `api.crossref.org/works?query.title=...` で確認する。確認できない項目は refs/references.bib に入れない。
2. **spec/outline.md を書く**: 冒頭に frontmatter 的メタ、続いて本文メモ(自由記述)、末尾に ```yaml ブロックで構造を入れる。スキーマ:
   ```yaml
   title: 文書タイトル
   doc_type: report   # paper / report / patent / web-docs
   approved: false    # 承認後に true に変える
   sections:
     - id: 01_intro
       file: 01_intro.md
       title: 背景
       purpose: この節で伝えること(1-2文)
       word_budget: 500   # 日本語は字数
       claims:
         - claim: 主張の一文
           refs: [key1, key2]   # bib キー。根拠ゼロの主張を置かない
       done_criteria:
         - 完了条件の箇条書き
   ```
3. **spec/glossary.md を書く**: 表形式 `| 正用語 | 禁止表記(カンマ区切り) |`。coverage.py が禁止表記を manuscript から検出する。
4. **spec/notation.md・spec/style.md を書く**: 記号・符号の正本表、文体規約。style は .textlintrc の設定と矛盾させない(単一正本)。
5. **`just coverage` を実行する**: 未承認でも YAML スキーマ解析が通り、`WARN: outline が未承認` が出ることを確認する。
6. **停止する**: outline+glossary+notation+style をユーザーに提示し、承認または修正指示を得る。承認を得たら `approved: true` に更新する。**承認前に原稿は1字も書かない**。

## Pitfalls
- 引用の捏造禁止。bib に入るのは実在確認を通った項目だけ。
- refs 空の claim を放置しない(根拠のない主張は本文でも書けない設計)。
- 文字数予算は現実的に。日本語は字数で指定する。
- outline の YAML を変えたら必ず coverage を再実行して解析が通ることを確認する。
