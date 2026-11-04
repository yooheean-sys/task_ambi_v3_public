---
name: longform-integrate
author: Hermes Agent
license: MIT
description: "Use when running final integration checks for human review."
version: 1.0.0
metadata:
  hermes:
    tags: [writing, integration, qa]
    parent: longform-writing-pipeline
---

# longform-integrate(統合検査と最終通読ゲート②)

全セクション完成後、機械検査の総合結果をまとめ、人間の全文通読に渡すのが仕事。承認までがゴール。

## When to Use
- 全セクション起草完了後の統合検査
- 改稿後のリリース前チェック

## 手順
1. **全ゲート実行**: `just lint` / `just check-refs` / `just coverage` / `just build`(PDF。LaTeX 未導入なら build-html で代替し明記する)。
2. **統合レポートを作成する**: 節別文字数(予算 vs 実測)/coverage 結果/引用監査(DOI 照合結果)/glossary 違反/render 警告。warning の自動消火をしない(報告に含める)。
3. **レビュー差分を用意する**: 前回承認タグ(`git tag approved-<n>`)との diff。初回は全文。
4. **停止する**: ユーザーに全文通読を依頼する(ゲート②)。承認後に `git tag approved-<n+1>` を打つことを提案する。

## Pitfalls
- 反復中の render は html、PDF はこの段階のみ(大型文書の LaTeX コンパイルは遅い)。
- ゲートを緑にするための用語変更は glossary 経由で行い、原稿直接のばらつき修正を乱発しない。
- markdown→docx 変換は対象外。docx が必要なら別工程で reference.docx+postprocess を追加する。
