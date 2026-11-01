---
name: langfuse-selfhosted
description: "Use when integrating or verifying Langfuse with Hermes."
version: 1.0.0
author: Hermes Agent
category: devops
license: MIT
metadata:
  hermes:
    tags: [langfuse, observability, evals]
    related_skills: [taskambi_kanban-agent-org]
---

# セルフホスト Langfuse 連携（events_only）

## When to Use

- Langfuse との連携・実測検証・API 可否の確認をするとき
- 評価ハーネス（データセット/実験/採点）を Langfuse 上に設計するとき
- SOUL.md / criteria.md 改訂の版管理を Langfuse Prompt Management に載せるとき

## 環境の不変条件

- self-hosted Langfuse は **events_only モード（取り込み専用）**。読み戻し系 API は無効、実行データの読み戻しは ClickHouse 直読みのみ
- 認証情報は `~/.hermes/.env` の `HERMES_LANGFUSE_PUBLIC_KEY` / `HERMES_LANGFUSE_SECRET_KEY` / `HERMES_LANGFUSE_BASE_URL`。認証は basic auth（`curl -u "$PK:$SK"`）。鍵を stdout に出さない
- Hermes の `observability/langfuse` プラグインは**書き出し専用（トレース送信のみ、読み戻し機能なし）**。連携は常に「Hermes→Langfuse の push」で設計する

## 実測 API 可否マトリクス

| 操作 | エンドポイント | 可否 |
|---|---|---|
| ヘルス確認 | `GET /api/public/health` | ✅ |
| Prompt Management | `GET /api/public/v2/prompts`（他 v2 prompts 系） | ✅ events_only でも動く |
| データセット作成 | `POST /api/public/v2/datasets` | ✅ |
| データセットアイテム投入 | `POST /api/public/v2/dataset-items` | ❌ 404 → **v1 `/api/public/dataset-items` を使う**（✅） |
| データセット削除 | `DELETE /api/public/datasets/{id}`（v1/v2 とも） | ❌ 405（無効）— UI から消す |
| トレース読み戻し | `GET /api/public/traces` | ❌ 404 → ClickHouse 直読み |
| スコア・run 投稿 | push 系（dataset-run-items / scores） | ✅ 採点は外部計算して POST |

可否の再確認は `scripts/probe_api.sh` を実行する（手で curl を組み立てない）。

## 連携設計の役割分担

- **実行は kanban が駆動する。Langfuse は実行を駆動しない** — 評価ハーネスの Langfuse の役割は「データセット登記簿（サンプルの input/expectedOutput 登録）+ バージョン横断のスコア表」に限定する
- 採点は外部（人間検収の結果のスコア化、または Hermes 自身をジャッジにした採点）で計算し、experiment 名を `soul-vN` のように付けると SOUL/criteria 改訂ごとの合格率・逸脱回数を UI で横断比較できる
- Prompt Management は SOUL.md / criteria.md 改訂の版管理庫に使える: production ラベル取得 → profile の SOUL.md へ書き出す sync スクリプトの形にする（Hermes 本体の変更は不要、spawn はファイルから読むだけ）。真実の源を 1 箇所に固定すること（推奨: Langfuse=版管理庫、profile の SOUL.md=デプロイ成果物。criteria.md は人間が直接編集するので git 管理向き）
- **LLM-as-judge は成果物の実体検証（CLI 再実行 + 独立再計算）の代わりにならない**。プロセス品質（逸脱・ループ・根拠の質）の補助指標としてのみ使う
- events_only ではトレース読み戻しができないため、**ジャッジへの入力は成果物・ログ・カードコメントを手元で組み立てる**。トレースを読ませるジャッジ設計は不可能

## 落とし穴

- データセットアイテム投入は v2 が 404 になる。v2 で失敗したら v1 旧 API に切り替える（スキーマは同一ではないので応答を見る）
- データセットの削除は API では不可（405）。検証用プローブのデータセットは名前に `delete-me` を含め、UI から手で消させる
- 実行データの確認は `docker exec langfuse-selfhosted-clickhouse-1 clickhouse-client` で default.events_core の count/max(start_time)。**時刻は UTC なので JST +9 で読む**
- プロンプト取得 401 は認証不足（.env 未読み込み）。`set -a; source ~/.hermes/.env; set +a` してから叩く
