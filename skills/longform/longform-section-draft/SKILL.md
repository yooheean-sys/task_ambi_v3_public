---
name: longform-section-draft
author: Hermes Agent
license: MIT
description: "Use when drafting one manuscript section under gate checks."
version: 1.0.0
metadata:
  hermes:
    tags: [writing, drafting]
    parent: longform-writing-pipeline
---

# longform-section-draft(1セクション起草とゲートループ)

kanban カード = 1 セクション。カードの完了条件 = 全ゲート緑 + diff 提示。人間の節単位承認は求めない(ゲートは最終通読に集約)。

## When to Use
- approved な outline の 1 セクションを起草するとき
- 既存節の大規模加筆(実質=起草)のとき

## 手順
1. **前提確認**: spec/outline.md の `approved: true` を確認。未承認なら起草せず longform-outline に返す。
2. **読むものを絞る**: 対象セクションの outline エントリ・glossary/notation/style・その refs の bib エントリ・隣接セクションのタイトルのみ。原稿全文は読まない(文脈一貫性は outline と notation が担う)。
3. **起草する**: manuscript/<file> に 1文1行で書く。見出しは outline の title に一致させる。引用は `[@key]` のみ。outline に無い主張が必要になったら勝手に書かず、outline への追加提案として止まる。
4. **ゲートを回す**: `just lint` → `just check-refs` → `just coverage` → `just build-html`。失敗は patch で修正する(再生成しない)。SKIP(ツール未導入)は報告に明記する。
5. **文字数を測る**: 予算±30%を目安に、超過/不足は削る・伸ばす提案付きで報告する。
6. **停止する**: ゲート状態・文字数・使用引用一覧を報告して完了。

## Pitfalls
- 他セクションのファイルを編集しない。
- bib に無いキーを書かない(check-refs が落とすが、書いた時点で手戻り)。
- 同一ゲートを3回連続で落としたら修正ループを打ち切り、原因を報告して止まる。
- markdown→docx 変換は対象外。docx の話が出たら明示的に切り離す。
