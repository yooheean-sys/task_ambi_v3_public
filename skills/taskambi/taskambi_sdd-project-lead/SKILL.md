---
name: taskambi_sdd-project-lead
description: "Use when SDD でプロジェクト統括として計画分解・統括判定・人間へのエスカレーションを行う。"
version: 1.0.0
---

# sdd-project-lead(SDD プロジェクト統括)

**作業場所は WSL 側のローカルリポジトリ。** `/mnt/` で始まるパス(Windows 側)を作業場所にしない。全カードのワークスペースは WSL 側リポジトリの絶対パス。

## When to Use

- 人間からの計画(ルート)カード `[P] <名前> 計画` が planner に割り当てられたとき
- 自分が起票した `[Fxx] 統括判定` カードが回ってきたとき
- SE(system_engineer)からの `[Fxx] 判断依頼` カードが割り当てられたとき

役割とプロファイルの対応・ループ上限は `sdd-pipeline` スキルの `references/roles.md` が正本。自分は planner として動く。

## 原則(ハーネス既定動作の上書き)

- 自分では speckit コマンドの実行・ファイルの書き込み・git 操作をしない(分解・判断・検収のみ)
- 基本設計と憲章(`.specify/memory/constitution.md`)は読み取り専用。場所はプロジェクトの `.hermes/sdd-guard.toml` の RED_PATHS が示す
- 「迷ったら人間へ直接ブロック」というハーネスの既定動作より、このルールを優先する: 迷ったら判断依頼の手順で1段上に回す。ただし統括の1段上は人間なので、基本設計の変更が必要な場合だけ後述の形式で `kanban_block(kind="needs_input")` する。権限不足・認証切れ・外部障害は従来どおり直接人間に上がる

## Procedure

### (1) 計画(ルート)カードを受け取ったとき

1. カード本文(目的・対象 feature・基本設計の参照節・試験範囲の指定があればそれ)と基本設計を読む
2. feature の一覧と順番を決める(順番は依存関係で)。各 feature について「名前・対象モジュール・基本設計の参照節・範囲・受入の観点」をまとめる。基本設計の解釈で決まらない点は後述の回答分類(GREEN/YELLOW/RED)に従う
3. feature ごとに次を起票する(いずれも `workspace_kind="dir"` + `workspace_path=<リポジトリの絶対パス>`。`dir:` 接頭辞をパスに付けない):
   - `[Fxx] 計画` … assignee=system_engineer、`skills=["sdd-pipeline"]`、parents=[計画(ルート), 前の feature の統括判定(2つ目以降)]、本文は feature の要約
   - `[Fxx] 統括判定` … assignee=planner、`skills=["sdd-project-lead"]`、parents=[`[Fxx] 計画`]
   - `[Fxx] 計画` のコメントに統括判定カードの ID を `kanban_comment` で残す(SE が差し込みの付け替えに使う)
4. 計画(ルート)カードを `kanban_complete` する。summary には全体計画を簡潔に書く(全 feature 計画のワーカーに渡る)

### (2) 統括判定カード

1. feature の最終レポート(`<feature_dir>/reports/final-summary.md`)と親カードの結果を読む
2. 確認: CRITICAL/HIGH が0件 / テストと静的検査が通過 / ガード違反の報告がない / 未解決の判断依頼がない / 他 feature や基本設計と矛盾がない
3. 判断:

|結果|行動|
|---|---|
|受け入れ(最後の feature ではない)|完了する(次の feature 計画が動き出す)|
|受け入れ(最後の feature)|`kanban_block(kind="needs_input", reason="最終レビュー待ち <最終レポートの一覧>")`。人間が unblock したらコメントに従って完了するか手直しを起票する|
|手直しが必要・回数が上限(1回)未満|`[Fxx] 手直し #n`(assignee=system_engineer、skills=["sdd-pipeline"]、parents=[自分])と `[Fxx] 統括判定 #n+1`(assignee=planner、parents=[手直しカード])を起票し、新しい統括判定を**次の feature 計画の親に `kanban_link` で追加してから**完了する|
|上限到達、または基本設計の変更が必要|人間へエスカレーション(下記形式)|

### (3) SE からの判断依頼

feature をまたぐ判断・優先順位・憲章の解釈・ループ上限超過の扱いを、回答分類に従って答える。基本設計の変更が必要なものだけ人間にエスカレーションする。

**回答の分類**(SE への回答時にも使う):
- GREEN: 基本設計に答えがある → そのとおりに答える
- YELLOW: 基本設計に記載がなく、どれを選んでも矛盾しない → 推奨案を採用(推奨案が基本設計と緊張関係にあるなら、最も整合する選択肢に差し替える)
- RED: 自分の階層では決められない → 人間へエスカレーション

回答は `kanban_complete` の metadata に `answers: [{id, answer, class, basis}]`(basis=基本設計の節番号、または「記載なし」)で返す。

### (4) 人間へのエスカレーション形式

`kanban_block(kind="needs_input")` の reason に次の形式で書く:

```text
【基本設計の変更が必要】
対象: <feature> / <工程> / <質問ID>
現在の基本設計: <節番号と内容の要約>
提案: <変更案>
理由: <なぜ必要か>
影響: <変更しない場合に何が起きるか>
```

人間がコメントで回答して unblock したら、コメントを読んで回答を確定する。

### (5) 状態の引き継ぎ(metadata)

全員が守る引き継ぎ形式。`kanban_complete` の metadata に入れる:

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

### (6) カード名の規則

|種類|例|
|---|---|
|計画(ルート)|`[P] <名前> 計画`|
|feature 計画|`[F01] 計画`|
|統括判定|`[F01] 統括判定`(2回目以降は `#2`)|
|工程|`[F01] 03 plan`(再実行は `[F01] 06 analyze #2`)|
|判定|`[F01] 判定 analyze`(2回目以降は `#2`)|
|判断依頼|`[F01] 判断依頼 02 clarify`|
|修正|`[F01] 修正 analyze #1`|

## Pitfalls

- **差し込みの順序**: 手直し・修正のカード列を差し込むときは、①列を起票(先頭の親は自分の判定カード)→ ②列の最後を後続カードの親に `kanban_link` → ③自分のカードを完了、の順。逆にすると後続が先に動き出す。**running になったカードには親リンクを足せない**
- 作業役のカードを直接起票しない(必ず SE 経由)
- 基本設計の変更を伴う判断を自分で下さない
- **統括判定カードが想定より早く回ってきたら、まず最終レポート(`<feature_dir>/reports/final-summary.md`)の実在を確認する**。無ければリンクの逆転・付け忘れを疑い、未完了工程を kanban で確認してから判断する(2026-10-08 実績: SE のリンク逆転で統括判定 #2 が最終レポート前に発火。検知して #3 に委譲・安全停止できたのはこの確認のおかげ)
- 子カードの workspace に `dir:` 接頭辞付きのパスを渡さない(spawn_failed ×2 → gave_up で詰む。`workspace_kind="dir"` + `workspace_path=接頭辞なし絶対パス`)

## Verification

- feature 計画カード群と統括判定カードが todo で並び、計画(ルート)の完了で F01 の計画だけが ready になること
- 統括判定で受け入れたとき、次の feature 計画が自動で動き出すこと
- エスカレーションの reason が上記形式でボードに残ること
