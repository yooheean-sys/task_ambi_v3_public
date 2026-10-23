---
name: vault_vtt_minutes
description: Use when VTT字幕→議事録→vault 00_inbox パイプライン（vtt-minutes）の保守・改修・テスト・トラブルシュートをするとき。Windows Downloadsの新着.vttを検出し議事録を${VAULT_NAME}の00_inboxへ保存する。
---

# vault_vtt_minutes — VTT字幕を議事録化して vault 00_inbox へ保存するパイプライン

## 全体構成

WSL2 の /mnt/c は inotify 非対応のため、ポーリングで新着検出する（デーモン不要）。

```
Windows Downloads に .vtt 新着
  → cron ジョブ vtt-download-watch（2分ごと、no-agent スクリプト）
  → HMAC-V2 署名付き POST → localhost:8644 webhook ルート vtt-minutes
  → agent セッションが日本語議事録を作成
  → ${VAULT_ROOT}/00_inbox/議事録_YYYY-MM-DD_HHMM_ベース名.md
```

## 構成要素

| 部品 | 場所 |
|---|---|
| cron ジョブ | `vtt-download-watch`（`*/2 * * * *`）。`hermes cron list`、実体は ${HERMES_HOME}/cron/jobs.json |
| 監視スクリプト | ${HERMES_HOME}/scripts/vtt_scan_post.py |
| seen 状態 | ${HERMES_HOME}/scripts/.vtt_seen.json |
| 監視先 | /mnt/c${USER_HOME_MAC}/Downloads（`*.vtt`、mtime 15秒未満はスキップ） |
| webhook ルート | ${HERMES_HOME}/webhook_subscriptions.json の `vtt-minutes` |
| ルート URL | http://localhost:8644/webhooks/vtt-minutes（subscriptions に url キーは存在しない。ポートは WEBHOOK_PORT から導出） |
| 保存先 inbox | ${VAULT_ROOT}/00_inbox |
| 汎用パターン解説 | hermes-webhook-file-trigger スキル |

## ルート vtt-minutes の仕様（2026-10-21 検証済み）

- `deliver: log` — 最終回答は Discord 等へ送らず gateway.log に記録するだけ（gateway/platforms/webhook.py で deliver=="log" はログ送り）。正式な成果物は inbox の議事録ファイル。旧仕様は discord 配信。
- `toolsets: ["file", "terminal"]` — JSON への手動追記キー。これがないと webhook agent は最小 toolset で read_file 等が使えず失敗する。`hermes webhook subscribe` CLI はこのキーを設定できない。
- prompt は `{file_path}` を受け取り、議事録を 00_inbox に保存させ、最終回答は「保存先パス＋要点」のみにする指示。保存失敗時はエラー内容と議事録本文を最終回答に含めて報告する（ログから復旧可能にする）。
- secret は同 JSON 内に保存。会話やログに出力しない。

## 議事録ファイル規約

- 名前: `議事録_<YYYY-MM-DD_HHMM>_<元ファイル名から拡張子を除いた名前>.md`。日時は `TZ=Asia/Tokyo date '+%Y-%m-%d_%H%M'` で取得。
- 冒頭に「読み込みファイル: <ファイル名>」と「取得元: <フルパス>」を記載。
- セクション: 【会議概要】【決定事項】【TODO（担当・期限）】【論点・保留事項】。話者発言は要約統合し、逐語は書かない。
- Obsidian 禁止文字（< > : " / \\ | ? *）をファイル名に使わない（元ファイル名に含まれる場合は置換）。
- 9p（Dropbox 同期）マウントのため、書き込みは write_file / Python open('w')。patch の rename-over 書き込みは Permission denied になることがある。
- inbox に置かれた議事録は週次ジョブ「00_inbox週次分類 (${VAULT_NAME})」（vault_inbox_classification スキル）が各ディレクトリへ分類する。

## 改修・テスト手順

1. prompt 変更: webhook_subscriptions.json を直接編集 → 次の POST でホットリロード（mtime 監視）。
   注意: `hermes webhook subscribe` での再登録は route を丸ごと再構築するため、手動追記した toolsets が消える（hermes_cli/webhook.py の _replace_subscription で確認済み）。CLI を使った場合は toolsets を再追記すること。
2. 動作テスト（seen 状態に触れず実ファイルも汚さない）:
   ```
   hermes webhook test vtt-minutes --payload '{"file_name":"x.vtt","file_path":"/path/to/x.vtt","source":"windows-downloads"}'
   ```
   → 202 accepted が即返る。agent 実行は非同期（検証時は約20秒）。/mnt/c/.../00_inbox/議事録_*.md の出現で完了判定。テスト後に成果物を削除して inbox を清掃する。
3. 監視スクリプトのリセット: .vtt_seen.json を丸ごと消すと再ベースライン（既存ファイルを無視して記録）。個別エントリ削除で当該ファイルを再トリガ。

## デバッグ

- gateway.log の `[webhook]` タグ: POST／署名／応答を確認。「response ready ... response=N chars」が応答完成の目印。
- agent セッション: state.db の sessions/messages（session_key がルート名 vtt-minutes で終わる）。assistant content が空の行は tool-call ターン。
- cron スクリプト失敗: executions.db の error 列に stderr traceback。failure_deliver（discord）にも通知される。
- webhook サーバ状態: `curl http://localhost:8644/health`

## 教訓

- drvfs（/mnt/c）では inotify が効かない → cron ポーリング一択（ネイティブ watcher は何も検知しない）。
- POST 成功後にのみ seen を更新 → 失敗したファイルは次 tick で自動再試行。
- deliver=log は agent モードでは有効。deliver-only モードでは log は拒否される（CLI バリデーション）。
- webhook ルートの「prompt に最終回答＝成果物」前提は、成果物をファイル保存する方式に変えると破綻する。deliver を log に変え、成果物の所在を最終回答で報告させる形に整理した。
