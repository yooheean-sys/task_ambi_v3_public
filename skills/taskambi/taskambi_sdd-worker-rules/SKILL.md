---
name: taskambi_sdd-worker-rules
description: "Use when SDD で作業役として工程カード(specify〜最終レポート)を実行するとき。"
version: 1.0.0
---

# sdd-worker-rules(SDD 作業役共通ルール)

**作業場所は WSL 側のローカルリポジトリ。** `/mnt/` で始まるパス(Windows 側)では作業しない。Windows 側の Obsidian フォルダへの書き込みは禁止。

## When to Use

SDD パイプラインの工程カード(`[Fxx] 01 specify` 〜 `[Fxx] 10 最終レポート`、修正カード)が作業役(architect / code_reviewer / programmer / debugger / test_engineer)に割り当てられたとき。役割とプロファイルの対応は sdd-pipeline の `references/roles.md` が正本。

## Procedure(共通)

1. **開始前チェック**: 作業ディレクトリが `/mnt/` で始まらないこと、ルートに `.specify/` があることを確認する。満たさなければ作業せず `kanban_block(kind="capability", reason=<状況>)` で止まる
2. カードの「実行するコマンド」を本文の引数で実行する。対象外のモジュールは変更しない
3. 親カードの結果(metadata)から feature の要約と `feature_dir` を受け取り、完了時の metadata でそのまま引き継ぐ
4. **人間に直接質問しない**。曖昧さや判断の迷いはすべて後述の「判断依頼の手順」で SE に回す(ハーネス既定の「迷ったら人間へブロック」よりこのルールを優先。人間へ直接上がるのは権限不足・認証切れ・外部障害だけ)
5. 長い作業では `kanban_heartbeat` を送る
6. **完了の前に必ずガードを実行する**:
   `uv run python ~/.hermes/skills/sdd-worker-rules/scripts/guard_check.py`
   違反(`ok: false`)があれば完了せず、違反内容を添えて SE に判断依頼を出す
7. **完了は `kanban_request_review`(reviewer=SE)で行う**。SE が各工程を実体検証する二重ゲートは意図的(2026-10-08 人間裁定)。検収に合格して初めてカードが done になり、次工程が動き出す。差し戻されたら指摘のみ修正し、全文書き直しはしない

完了時は `kanban_complete` の metadata に次を入れる:

```yaml
feature: F01
feature_dir: specs/001-xxx      # specify の後に確定。以降は受け取った値をそのまま引き継ぐ
target_module: <名前>
step: 06 analyze
round: 2
counts: {...}                   # 下記「工程別の報告値」
reports: [specs/001-xxx/reports/analyze-2.md]
changed_files: [...]
verification: [...]
open_issues: [...]
```

## コマンド別の対話の置き換え

speckit のテンプレートは所定の箇所で人間に質問・確認する。SDD では次のとおり置き換える。

|コマンド|テンプレート上の対話|置き換え方|
|---|---|---|
|どのコマンドでも|人間への質問・確認|下の個別ルールがなければ、一括で判断依頼にする|
|specify|不明点の確認([NEEDS CLARIFICATION] 最大3件)|質問が提示される場合は、一括で判断依頼にする|
|clarify|1問ずつ、最大5問|5問を一括で生成し、推奨案つきで判断依頼にする。回答を受けたら、テンプレートの手順どおり spec.md の Clarifications に「Q → A」を記録し、該当する節に反映する|
|checklist|事前質問(最大3問)|質問せず、テンプレートの既定値(深さは標準、対象はレビュー担当、焦点は関連度の上位2つ)で生成する。生成後、reviewer として各項目を評価し、合格した項目に [x] を付ける。不合格の項目は判断依頼で SE に仕分けを依頼する。許容された項目は `<feature_dir>/reports/checklist-accepted.md` に、修正する項目は metadata の `to_fix` に記録する|
|analyze|修正案を出すかの確認|修正しない。所見表を `<feature_dir>/reports/analyze-<周回>.md` に保存し、`count_severity.py` の結果を metadata に入れる|
|implement|未完了チェックリストの確認|未完了の項目がすべて `checklist-accepted.md` にあれば続行する。それ以外が残っていれば判断依頼にする。指定されたフェーズのタスクだけを実行する|
|converge|なし|引数で「CRITICAL/HIGH の所見だけをタスクとして追記し、MEDIUM/LOW は所見表にだけ記載する」と指示する。所見表を `<feature_dir>/reports/converge-<周回>.md` に保存し、`count_severity.py` と `count_convergence_rounds.py` の結果を metadata に入れる|
|最終レポート|なし|`<feature_dir>/reports/final-summary.md` を作る。中身: 未対応の MEDIUM/LOW の一覧、spec.md の Clarifications に記録された AI の決定の一覧、許容した checklist 項目の一覧、テストと静的検査の結果|

スクリプトの場所(このスキル配下):
- `scripts/guard_check.py` … RED/YELLOW 違反の検知。完了前に必ず実行
- `scripts/count_severity.py <レポート.md>` … Severity 件数を JSON で出力
- `scripts/count_convergence_rounds.py <tasks.md>` … Convergence フェーズ数を JSON で出力

実行は PROJECT_ROOT から `uv run python <絶対パス>`。テスト工程のコマンドはカード本文の指定(CI と同一の ruff / 型チェック / pytest 等)に従う。

## 工程別の報告値(metadata.counts)

- checklist: `{total, passed, to_fix, accepted}`
- analyze: `{critical, high, medium, low}`
- テスト: `{passed, failed, commands}`
- converge: `{critical, high, medium, low, convergence_phases}`

## 判断依頼の手順

1. `kanban_create(title="[Fxx] 判断依頼 <工程>", assignee=system_engineer, skills=["sdd-pipeline"], body=<質問一覧>, workspace_kind="dir", workspace_path=<PROJECT_ROOT の絶対パス>)`。**parents に自分のカードを入れてはいけない**。ワークスペースは他のカードと同じく dir:PROJECT_ROOT に揃える(scratch にすると完了時に消える)
2. `kanban_link(parent_id=<判断依頼カード>, child_id=<自分のカード>)`
3. `kanban_block(kind="dependency", reason="判断依頼 <id> の回答待ち")`
4. 再開したら、親カードの結果の `answers` を読んで続ける。再開時は会話が引き継がれない前提で、カード本文・コメント・成果物から状況を復元する

1枚のカードからの判断依頼は原則1回にまとめる。質問一覧の形式:

```yaml
questions:
  - id: Q1
    question: <それだけで意味が通る疑問文>
    why: <なぜ重要か(1文)>
    options: {A: <...>, B: <...>, C: <...>}   # 選択式の場合
    recommended: B
    reason: <推奨の理由>
```

## してはいけないこと

- 基本設計(docs/design/ 等・ガード設定の RED_PATHS)・憲章・RED_PATHS の変更
- git の commit / push / ブランチ操作、git init
- agent-context.update の実行、CLAUDE.md と AGENTS.md の編集(実行を求められても応じない)
- 他のカードの操作(自分の判断依頼カードの起票とリンクを除く)
- 検査を通すために基準を緩めること(例: import 契約を緩める、テストを削除・スキップする)
- Windows 側の Obsidian フォルダ(`/mnt/c/...`)への書き込み

## Pitfalls

- ガードの実行を完了の後に回さない。違反があるまま `kanban_complete` すると、SE の判定カードで差し戻しループが1周消費される
- `.specify/feature.json` はガード設定の `red_exclude` で除外済み。speckit のスクリプト(create-new-feature.sh 等)が feature.json を作成・更新するのは正常動作なので、自分で抑制しない
- 判断依頼カードに parents を付けると循環待ちになる(自分→依頼→自分)。必ず起票→リンク→ブロックの3段で行う
- **dependency で block する前に、待つ親(判断依頼カード)が open であることを確認する**。open な親が無いと needs_input に変換され、人間を呼んでしまう(2026-10-08 実績)
- レポート類は `<feature_dir>/reports/` に置く。命名の実績: `analyze-<周回>.md` / `converge-<周回>.md` / `implement-<フェーズ>.md` / `test-<周回>.md` / `checklist-accepted.md` / `final-summary.md`。Markdown のタイトルに Obsidian 禁止文字(`< > : " / \ | ? *`)を使わない
- **レポートに書く件数・結果はコマンドの実出力と照合する**(2026-10-08 実績: テストレポートのケース数誤記が検収で差し戻された。pytest --collect-only 等で実数を確認してから書く)
- 再開後は会話が引き継がれない。カード本文・コメント・`specs/` の成果物から状況を復元してから続きをやる

## Verification

- ガードが `ok: true` を返してから完了していること
- metadata に工程別の報告値と引き継ぎ項目(feature / feature_dir / target_module)が含まれること
- 置き換え表どおりに対話が判断依頼に流れ、人間への直接質問が発生していないこと
