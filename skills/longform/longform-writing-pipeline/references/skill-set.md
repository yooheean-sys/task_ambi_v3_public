# 分担スキル設計 — longform pipeline の実行スキル群

実装状況(2026-11-04): 5スキル作成済み。`longform-project-init` / `longform-outline` / `longform-section-draft` / `longform-revise` / `longform-integrate` を skill_view で参照。

方針: 決定論的チェックは justfile に置き、スキルは「判断・オーケストレーション・ゲート」だけを持つ。スキルから just ターゲットを呼ぶのは正しいが、just で書けるものをスキルにしない(lint実行・DOI照合・renderは just ターゲット)。

| skill | 責務 | 入力 | 出力 | 停止点 |
|---|---|---|---|---|
| longform-project-init | リポジトリ雛形生成 (_quarto.yml, spec/, manuscript/, refs/, justfile, .textlintrc+prh辞書) | プロジェクト名・文書種別 | 雛形一式 | なし(実行系) |
| longform-outline | outline+glossary+notation+style の生成 | トピック・ソース・bib | spec/*.md | 人間承認ゲート① |
| longform-section-draft | 1セクション起草+ゲート修正ループ | outlineの該当エントリ+glossary+style+その節のbibキー | manuscript/NN_xxx.md | ゲート緑+diff提示 |
| longform-revise | 人間フィードバックを targeted patch で適用 | レビューコメント+diff | patch適用後の節+pandiff/latexdiff | ゲート緑 |
| longform-integrate | 全体統合検査+最終 render | manuscript全体+spec | coverage/consistencyレポート+PDF | 人間承認ゲート② |

規約:
- kanban カード = 1セクション。カード完了条件 = just lint/check-refs/coverage が緑 + render 成功 + diff 提示。
- 引用は起草時に [@key] でのみ挿入(keyはbib由来)。bibに無いキーは just check-refs が落とす。
- 1文1行。節の部分再生成は禁止(patch のみ)。
- DOCX 変換(reference.docx・段番号postprocess)はスコープ外で後から longform-project-init に追加可能。スキル構成は変わらない。

justfile が持つべきターゲット: lint(textlint+vale)/check-refs(キー整合+Crossref/OpenAlex のDOI解決・メタデータ一致照合)/coverage(outline主張の本文逆引き)/build(quarto render)/diff(pandiff)。

実装メモ(2026-11-04): check-refs の第一層は pandoc citeproc ではなく scripts/check_refs.py(自前パーサ)が担当。pandoc 無しでも第一層を成立させるため。第二層(DOI解決+タイトル一致)も同スクリプトが Crossref API で実施。coverage は scripts/coverage.py(yaml不要の専用パーサ)。