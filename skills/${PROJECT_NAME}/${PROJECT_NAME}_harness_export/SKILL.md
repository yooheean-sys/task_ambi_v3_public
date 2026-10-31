---
name: ${PROJECT_NAME}_harness_export
description: "Use when ${REPO_NAME} のハーネス変更を ${REPO_NAME}_public へ公開するとき。"
version: 1.0.0
author: ${USER_NAME_LOWER}
license: private
metadata:
  hermes:
    tags: [task_ambi, harness, export, migration]
---

# ハーネス エクスポート（正本 → 公開）

正本 `${REPO_NAME}`（`${REPO_ROOT}`）で変更したハーネスを、
公開リポジトリ `${REPO_NAME}_public`（`${REPO_ROOT}_public`）
へ反映して公開する手順。移行の入口はこの 1 本道であり、別経路で同じ結果を作らない。

ドメイン規程（配布の契約・落とし穴）は `${PROJECT_NAME}_harness_distribution`、導入先側は
`${PROJECT_NAME}_harness_import` を参照する。

## 常時ルール

- 公開側は生成物。手編集で修正を終わらせず、正本を直してから生成・同期する。
- 生成器の `make_harness_public.py` の `main()` は公開先を初期化する（`.git` 以外消去）。
  **実在する公開作業ツリーへ直接実行しない**。検証は隔離生成 → 差分同期で行う。
- 同期では `.git` と実 `.env` を絶対に触らない。削除も差分に限定し、削除物は退避保存する。
- 公開側 commit の pre-commit `secret-scan` は正本の F4/F10 語群を実行時読み込みして
  ステージ内容・パス名・`.env` 実値・汎用鍵形式を検査する。**`--no-verify` で飛ばさない**。
- push はユーザー手動（WSL に認証経路がない）。依頼してから `ls-remote` で一致を確認する。
- 機密値・反映コマンドをログや成果物に書かない。証跡は `~/${KANBAN_RUNS_DIR}/<作業>_<日付>/outcome/`。

## 編集対応表（正本 harness/ 配下のみ）

| 変更内容 | 編集場所 |
|---|---|
| MCP サーバー | `harness/mcp.json`（正本） |
| hooks | `harness/hooks.json` ＋ `harness/agent-hooks/` |
| スキルの配布/除外 | `harness/skills.txt` ／ `harness/skills_ignore.txt`（両方への重複はエラー） |
| SOUL・25役 | `harness/SOUL.md`、`harness/souls/<役名>/SOUL.md`、`harness/profiles.txt` |
| criteria・cron | `harness/criteria/`、`harness/cron/jobs.json` |
| 導入ロジック・検証 | `harness/install_local.sh`、`harness/integration_settings.py`、`tests/` |
| ~~`harness/config.yaml`~~ | **編集しない**（旧スナップショット。配布・参照の対象外） |

## 手順

1. **変更前状態を確認**: 両リポジトリの `git status` と HEAD を取得し、未コミット差分を把握する。
   過去の要約より現物を優先する。
2. **正本を編集**（上の対応表どおり）。置換対象の実値を直書きした場合は正方向テーブルに語を
   追加する必要があるか確認する（`scripts/harness_replacements.py`）。
3. **全検証＋隔離生成**:

   ```bash
   cd ${REPO_ROOT}
   uv run python tests/verify_harness_skill_allowlist.py
   ```

   単体試験・隔離生成（two_skill と full）・F10 機密 0 件・再生成冪等・25役導入・再適用・
   機密スキャンまで一括。**全チェック exit 0 を確認してから次へ進む**。
   `summary.json` の `full_public` パスが検証済み生成物。
4. **差分同期**: `full_public` と公開作業ツリーの差分だけを反映する。
   同期は plan → apply の 2 段階で行い、apply 後に次を検証する:
   stage と全ファイル一致、`.env` の inode/size/mtime 不変、公開側 HEAD 不変、
   削除ファイルが退避済み、空ディレクトリ残骸 0。同期スクリプトが無い場合は
   plan 差分を出して目視確認してから適用する（一度に全部上書きしない）。
5. **正本を commit**。公開側も commit する（secret-scan が自動実行され Passed が gate）。
6. **push をユーザーに依頼**し、完了後 `GIT_TERMINAL_PROMPT=0 git ls-remote origin refs/heads/main`
   で両リポジトリの local = remote を確認する。
7. **証跡を保存**: `~/${KANBAN_RUNS_DIR}/<作業名>_<日付>/outcome/` に `summary.json`・
   同期 plan/result・レビュー結果があればそれも保存する。

## 落とし穴

- 検証で RED が出たら生成・同期に進まない。部分緑での公開はしない。
- 同期の削除対象が想定外に広い場合は停止して差分を見る（ skills 大掃除が意図せず走ることがある）。
- 正本側の commit を忘れると、次の検証が別 HEAD で動く。正本・公開側の両方を commit する。
- 公開 README は生成物（`make_harness_public.py` の `README_TEXT`）。README 修正は生成元へ。

## references

- `docs/harness_operations.md` §1 — 定例フロー
- `docs/harness_integration_migration.md` — MCP/hooks 部分移行の契約
- `docs/harness_skill_allowlist.md` — skills.txt／skills_ignore.txt の仕様
- `docs/harness_manual_import.md` — 自動移行しないプラグイン・公式スキルの手動手順
