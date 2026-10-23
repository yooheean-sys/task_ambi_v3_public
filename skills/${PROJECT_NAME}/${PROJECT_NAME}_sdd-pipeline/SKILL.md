---
name: ${PROJECT_NAME}_sdd-pipeline
description: "Use when SDD の SE として工程カードの起票・判定・修正ループ制御を行う。"
version: 1.0.0
---

# sdd-pipeline(SDD system-engineer)

**作業場所は WSL 側のローカルリポジトリ。** `/mnt/` で始まるパス(Windows 側)を作業場所にしない。全カードのワークスペースは WSL 側リポジトリの絶対パス。

## When to Use

- 統括(planner)が起票した `[Fxx] 計画` カードが system_engineer に割り当てられたとき
- 自分が起票した `[Fxx] 判定 *` カードが回ってきたとき
- 作業役からの `[Fxx] 判断依頼` カードが割り当てられたとき
- 統括からの `[Fxx] 手直し #n` カードが割り当てられたとき

役割とプロファイルの対応・ループ上限は `references/roles.md` が正本(他スキルはこれを参照する)。

## 原則(ハーネス既定動作の上書き)

- 自分では speckit コマンドの実行・ファイルの書き込み・git 操作をしない
- 迷ったら判断依頼の手順で統括に回す。人間へ直接ブロックしてよいのは権限不足・認証切れ・外部障害だけ(人間へのエスカレーションは統括だけが行う)
- 判定カードの完了は、後続カードへの付け替え(下記「差し込みの原則」)より**後**に行う
- 各工程カードは完了時に review 状態になり、自分(SE)がレビュアーとして呼ばれる(二重ゲート。2026-10-08 人間裁定で採用)。実体で検証し、合格なら承認・不合格なら `kanban_request_changes` で差し戻す。判定カードはそのうえで metadata の件数を使って制御判断する

## Procedure

### (1) `[Fxx] 計画` カードを受け取ったとき

1. 親カードの結果(統括の全体計画)・カード本文(feature の要約)・コメント(統括判定カードの ID)を読む
2. 第1波を起票する(下の工程表)。各カードの parents は「`[Fxx] 計画`」と「直前のカード」。本文は (5) のテンプレート。試験範囲の指定があれば、その工程までだけを起票する
3. `判定 analyze` を統括判定の親に `kanban_link` で追加する
4. `[Fxx] 計画` を完了する。summary には feature の要約(対象モジュール・基本設計の参照節・受入の観点)を書く

工程と担当(起票は2回に分ける。implement のフェーズ数は tasks.md ができるまで分からないため):

|起票|順|カード|担当|skills|
|---|---|---|---|---|
|第1波|01|specify|architect|sdd-worker-rules, speckit-specify|
||02|clarify|code_reviewer|sdd-worker-rules, speckit-clarify|
||03|plan|architect|sdd-worker-rules, speckit-plan|
||04|checklist|code_reviewer|sdd-worker-rules, speckit-checklist|
||-|判定 checklist|system_engineer|sdd-pipeline|
||05|tasks|architect|sdd-worker-rules, speckit-tasks|
||06|analyze|code_reviewer|sdd-worker-rules, speckit-analyze|
||-|判定 analyze|system_engineer|sdd-pipeline|
|第2波|07|implement(tasks.md の `## Phase <番号>:` ごとに1枚)|programmer|sdd-worker-rules, speckit-implement|
||08|テスト|test_engineer|sdd-worker-rules|
||-|判定 テスト|system_engineer|sdd-pipeline|
||09|converge|code_reviewer|sdd-worker-rules, speckit-converge|
||-|判定 converge|system_engineer|sdd-pipeline|
||10|最終レポート|code_reviewer|sdd-worker-rules|

### (2) 判定カードの判断表

件数は作業役が metadata で報告した値を使い、SE は数え直さない。converge の周回数は作業役が報告する `convergence_phases` を正とする。ループ上限: checklist 修正1回 / analyze 3回 / テスト修正3回 / converge 3回(統括の手直しは1回)。

|判定|結果|行動|
|---|---|---|
|checklist|修正項目なし|完了する|
|checklist|修正項目あり・上限未満|修正(architect)→ checklist 再評価(code_reviewer)→ 判定 checklist #2 を差し込み、05 tasks に付け替える|
|analyze|CRITICAL/HIGH が0件|第2波を起票し、10 最終レポートを統括判定の親に追加する|
|analyze|CRITICAL/HIGH あり・上限未満|修正(architect。指摘 ID を本文に列挙)→ analyze #n+1(code_reviewer)→ 判定 analyze #n+1 を差し込み、統括判定に付け替える|
|テスト|通過|完了する|
|テスト|失敗・上限未満|修正(debugger)→ テスト #n+1(test_engineer)→ 判定 テスト #n+1 を差し込み、09 converge に付け替える|
|converge|CRITICAL/HIGH が0件|完了する(最終レポートが動き出す)|
|converge|CRITICAL/HIGH あり・上限未満|追記された Convergence フェーズの implement(programmer)→ テスト → 判定 テスト → converge #n+1 → 判定 converge #n+1 を差し込み、10 最終レポートに付け替える|
|どの判定でも|上限到達、またはガード違反の報告|統括に判断依頼を出す|

### 差し込みの原則(修正・再実行カードを挟むときの順序)

1. 差し込むカード列を起票する(先頭の parents は自分の判定カード)
2. 列の最後のカードを、まだ動いていない後続カード(次の工程・最終レポート・統括判定など)の親として `kanban_link` で追加する
3. その後で、自分の判定カードを完了する

順番を逆にすると後続カードが先に動き出す。**running になったカードには親リンクを足せない。**

**link の向きを間違えない**(2026-10-08 に1度逆転事故あり)。ルールはただ1つ: **child は parent の完了を待つ**。

- 最終レポートを統括判定の前に挟む正しい形: `kanban_link(parent_id=<10 最終レポート>, child_id=<統括判定>)` → 統括判定が最終レポートの完了を待つ
- 誤: `kanban_link(parent_id=<統括判定>, child_id=<10 最終レポート>)` → 最終レポートが統括判定を待ってしまいデッドロックする

link 後は `kanban_show <child>` で parents が意図どおりか必ず確認する。

### (3) 第2波の起票

- implement は tasks.md の `## Phase <番号>:` 見出しごとに1枚起票し、順番につなぐ。本文に「このフェーズのタスクだけを実行する」と書く
- implement の後に 08 テスト → 判定 テスト → 09 converge → 判定 converge → 10 最終レポート をつなぐ

### (4) 作業役からの判断依頼への回答

回答の分類(根拠=基本設計の節番号、または「記載なし」を添える):
- GREEN: 基本設計に答えがある → そのとおりに答える
- YELLOW: 記載がなく、どれを選んでも基本設計と矛盾しない → 推奨案を採用(緊張関係があるなら最も整合する選択肢に差し替え)
- RED: 自分の階層では決められない → 統括に判断依頼を出す

checklist の不合格項目の仕分け基準:
- 修正: [Gap] / [Conflict] / [Ambiguity] のうち、機能要件・受入基準・セキュリティ・データ整合性に関わる項目
- 許容: それ以外(表現の改善・軽微な網羅性など)
- 修正に基本設計の変更が必要なら RED

回答は `kanban_complete` の metadata に `answers: [{id, answer, class, basis}]` で返す。同じカードにある GREEN/YELLOW の回答は先にコメントに残し、RED の回答が来たらまとめて完了する。

### (5) 工程カードの本文テンプレート

```text
## 実行するコマンド
/speckit-<cmd> <引数>

## 対象
作業場所: <PROJECT_ROOT>(WSL側のローカルリポジトリ。/mnt/ 配下では作業しない)
feature_dir: 親カードの結果から引き継ぐ(specify の前は未定)
対象モジュール: <名前>(これ以外は変更しない)

## 参照
基本設計: docs/design/ の <節>(読み取り専用)
詳細設計: specs/(実装とずれたら同期してよい)

## 追加指示
<工程ごとの指示。例: analyze の指摘 A3 と A7 を修正する>

## 完了条件
<この工程の完了条件>
```

コマンドの引数には毎回、次を含める: 対象モジュール以外は変更しない / 基本設計は読み取り専用 / git init・commit をしない / agent-context.update を実行しない / CLAUDE.md と AGENTS.md を編集しない。

### (6) 手直しカード(統括から)を受け取ったとき

統括の指示に応じて必要な工程(修正 → テスト → converge など)を起票し、列の最後を新しい統括判定の親に追加してから完了する。

### (7) 状態の引き継ぎ(metadata)

`kanban_complete` の metadata に入れる(全員共通):

```yaml
feature: F01
feature_dir: specs/001-xxx      # specify の後に確定。以降は受け取った値をそのまま引き継ぐ
target_module: <名前>
step: 06 analyze
round: 2
counts: {critical: 0, high: 1, medium: 3, low: 2}   # 該当する工程のみ
reports: [specs/001-xxx/reports/analyze-2.md]
changed_files: [...]
verification: [...]
open_issues: [...]
```

### (8) 判断依頼の手順(自分が統括に出すとき)

1. `kanban_create(title="[Fxx] 判断依頼 <工程>", assignee=planner, skills=["sdd-project-lead"], body=<質問一覧>, workspace_kind="dir", workspace_path=<PROJECT_ROOT の絶対パス>)`。parents に自分のカードを入れてはいけない。ワークスペースも dir:PROJECT_ROOT に揃える
2. `kanban_link(parent_id=<判断依頼カード>, child_id=<自分のカード>)`
3. `kanban_block(kind="dependency", reason="判断依頼 <id> の回答待ち")`
4. 再開したら親カードの結果の `answers` を読んで続ける。再開時は会話が引き継がれない前提で、カード本文・コメント・成果物から状況を復元する

質問一覧の形式:

```yaml
questions:
  - id: Q1
    question: <それだけで意味が通る疑問文>
    why: <なぜ重要か(1文)>
    options: {A: <...>, B: <...>, C: <...>}   # 選択式の場合
    recommended: B
    reason: <推奨の理由>
```

### (9) カード名の規則

工程: `[F01] 03 plan`(再実行は `#2`)/ 判定: `[F01] 判定 analyze` / 判断依頼: `[F01] 判断依頼 02 clarify` / 修正: `[F01] 修正 analyze #1`

## Pitfalls

- 全カードを `workspace_kind="dir"` + `workspace_path=<リポジトリの絶対パス>` で作る。`workspace_path` に `dir:` 接頭辞を付けない(spawn_failed ×2 → gave_up で恒久詰み)
- 工程・判定・修正カードの parents には、直前のカードに加えて `[Fxx] 計画` も付ける(feature 計画に進み具合が表示され、要約が全工程のワーカーに渡る)
- 2つ目以降の feature 計画には前の feature の統括判定も親に付いている(feature を1つずつ順に進めるため)。統括が張る
- 起票コマンドの本文が長いときは、承認ゲートで詰まないよう内容は簡潔に保つ
- 1枚のカードからの判断依頼は原則1回にまとめる(同じカードでブロックを繰り返さない)
- **parents は起票時に渡す**。parents を空で起票すると、依存先が全部 done のカードは即 ready になり、親リンクを後足しする間に dispatcher が拾う race がある(2026-10-08 実績: SE が起票後補完で間に合わせたが危険)。やむなく後足ししたら `kanban_show` で `dependency_wait` (gated) を確認する
- **dependency で待つときは、待つ親カードが open(未完)であることを確認してから block する**。open な親が無い状態で `kanban_block(kind="dependency")` すると needs_input に変換され、人間を呼んでしまう(同実績: 統括判定 #2)

## Verification

- 第1波の起票後、ボードに 01 specify だけが ready になり、残りが todo で並ぶこと
- 判定 analyze 合格時に第2波と最終レポート→統括判定の依存が正しく張られること
- 差し込み時に後続カードが premature に動き出していないこと(Events に `dependency_wait` があるか)
