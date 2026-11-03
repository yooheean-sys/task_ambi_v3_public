---
name: taskambi_conduct_review
description: Use when taskambi スキル群使用後の行動履歴を検査し、想定外動作の改善事項を挙げて修正するとき（hooks 自動起動 or ユーザー明示指示）。
version: 1.1
author: ${USER_NAME_LOWER}, Hermes Agent
license: private
tags: [taskambi, self-improvement, review]
related_skills: [taskambi_kanban-agent-org, taskambi_boot, taskambi_project]
---

# taskambi_conduct_review — 行動履歴検査と改善

taskambi スキル群を使い終わったセッションを、taskambi の規約・手順に照らして検査し、
想定通り動かなかった部分の改善事項を挙げて修正する専用スキル。
hooks（`taskambi-review.py`）が `on_session_end` で自動起動するか、ユーザーが明示的に
「検査して」と指示したときに発動する。

## When to Use

- hooks から「[taskambi 自動検査] …」というプロンプトで起動されたとき
- ユーザーが taskambi 作業後に「検査して」「改善事項をまとめて」と指示したとき
- 使わない: taskambi 作業中（まだ使い終わっていない）、他スキルの個別デバッグ

## 手順

1. **対象の特定**: hooks 起動ならプロンプトに session_id が含まれる。無い場合は
   `session_search` で直近の taskambi スキル使用セッションを特定する。

2. **行動履歴の取得**: `session_search(session_id=<対象>)` で当該セッションの
   ユーザー指示・アシスタント応答・tool 呼び出しを取得する。

3. **検査観点の収集**: 使用された各 taskambi スキル（`taskambi_*`）を
   `skill_view` で読み込み、以下の節を検査基準として抽出する:
   - `## してはいけないこと` / `## Pitfalls` / `## 落とし穴` に挙げられた既知の失敗パターン
   - `## Verification` / `## 検証` の必須確認項目
   - SOUL の必須防衛条項（全複製共通、`taskambi_kanban-agent-org` 正本）

4. **照合と判定**: 各観点について「守られた」「守られなかった」「守る機会がなかった」
   の3分類で判定する。守られなかった場合、具体的にどの行動が逸脱したかを
   セッション内の事実（tool 呼び出し・メッセージ）で裏付ける。

5. **改善事項の挙げ**: 守られなかった観点ごとに改善事項を挙げる。改善事項は
   以下の2区分に分ける:
   - **自動適用可**: hook スクリプトの検出条件調整、本スキル自身の検査観点追加、
     docs/操作手順の文言修正、コメント欄・記録ファイルの補足など
   - **人間承認必要**: SOUL.md 改訂、スキル本体の規約変更、権限・承認フローの変更

6. **修正の適用**:
   - 自動適用可のものは即座に修正し、修正内容を報告する。
   - 人間承認必要のものは修正案（差分の要約）を出して止まり、ユーザーに報告する。
     SOUL 改訂は人間承認制（`taskambi_sync_project_lead` の規約）を守る。

7. **証跡の保存**: 検査結果と適用した修正を
   `~/.hermes/agent-hooks/taskambi-review/results/<日付>_<session短id>.md` に保存し、
   本ターン最後にユーザー（または後続ターン）から参照可能にする。

## hooks 連携（起動元の仕組み・切り分け用）

- 起動元 hook: `~/.hermes/agent-hooks/taskambi-review.py`（config.yaml `hooks:` の
  `on_session_end` に登録・timeout 30s）。detect（検出）→ 120 秒 idle 待機 →
  新規ユーザーメッセージが無ければ本スキルを
  `hermes --skills taskambi_conduct_review --resume <session_id> --accept-hooks chat -q "<検査プロンプト>" --oneshot`
  で起動（`--resume` なので検査結果は同じセッションに残る）。
- state・ログ・証跡: `~/.hermes/agent-hooks/taskambi-review/` 配下
  （state.jsonl / log.jsonl / pending.json / results/）。
- 動作確認: `hermes hooks list` / `hermes hooks doctor` /
  `hermes hooks test on_session_end`。
- 検出メカニズム（検出漏れの切り分け用）: session DB（default profile は
  `~/.hermes/state.db`・読み取り専用 URI で接続）の `messages.tool_calls` JSON を
  パースして taskambi スキル名を抽出する。バッチ呼び出しは `tool_call` ラッパー内の
  `calls[]` に入り、その行の `tool_name` 列は NULL になるため tool_name では検出できない。
  content への LIKE 検索はアシスタント本文の言及まで拾って誤検出するので JSON パースが正。

## 報告形式

```
## taskambi 行動履歴検査結果（session <短id>）
### 使用されたスキル
- taskambi_xxx, taskambi_yyy
### 検査結果
- <観点>: 守られた / 守られなかった（<事実>）/ 該当なし
### 改善事項（自動適用）
- <内容> → 適用した修正: <概要>
### 改善事項（人間承認必要）
- <内容> → 修正案: <概要>
### 証跡
- ~/.hermes/agent-hooks/taskambi-review/results/<ファイル>
```

## してはいけないこと

- セッション内の他のタスクの進行中に検査を始めない（hooks の idle 待機が
  中断済みとして解除されてから起動されているはず。プロンプトが古い場合は
  session DB で新規ユーザーメッセージの有無を確認してから着手する）
- SOUL.md・スキル本体の規約を勝手に変更しない（人間承認制）
- セッション内の他アシスタントの判断を勝手に上書きしない（検査は事後の観察であり、
  過去のターンを「訂正」するのではない）
- 検査プロセスからさらに taskambi 作業を始めない（本スキルは検査・改善のみ。
  新たな作業が必要な場合は報告して止まり、ユーザーが指示するのを待つ）
- 環境変数 `HERMES_TASKAMBI_REVIEW=1` がついた検査プロセスから hooks を
  再起動しない（hooks 側が自己スキップするが、本スキルからも呼ばない）

## Verification

- session DB で当該 session_id の全メッセージを確認し、検査漏れがないこと
- 改善事項すべてに「守られた / 守られなかった / 該当なし」の判定がついていること
- 自動適用した修正は報告に含まれていること
- 証跡ファイルが存在すること
