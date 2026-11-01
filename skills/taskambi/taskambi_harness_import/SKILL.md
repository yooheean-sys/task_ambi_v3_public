---
name: taskambi_harness_import
description: "Use when ${REPO_NAME}_public から導入先の Hermes へハーネスを導入・更新するとき。"
version: 1.0.0
author: ${USER_NAME_LOWER}
license: private
metadata:
  hermes:
    tags: [task_ambi, harness, import, migration]
---

# ハーネス インポート（公開物 → 導入先）

公開リポジトリ `${REPO_NAME}_public` を導入先マシンの Hermes へ導入・更新する手順。
経路は **`install_local.sh` の 1 本**であり、他の経路で同じ結果を作らない。

生成側（正本 → 公開）は `taskambi_harness_export`、ドメイン規程は
`taskambi_harness_distribution` を参照する。

## 常時ルール

- 導入先は**初期設定済み**の Hermes ホーム（`config.yaml` が存在する）であること。
  ない状態では installer は停止する。勝手に初期化・続行しない。
- 経路の比較: `hermes profile install` 単体は不完全（単一プロファイル化のみ・25役なし・
  設定反映なし）。Hermes 本体は実行時に `mcp.json` を読まず、MCP は config の `mcp_servers`、
  hooks は `hooks` ブロックから解決されるため、`integration_settings.py` 経由の変換が必須。
  config.yaml 等の手動コピーは禁止（利用者設定を壊す・競合検知なし）。
- 導入スクリプトが作るプロファイルは `hermes profile update` の対象外。**更新は installer 再実行**。
- installer は hooks の初回承認を代行しない。allowlist・`hooks_auto_accept` を勝手に変えない。
- `cron/jobs.json` の `enabled/state` は変更せずそのまま配置する。**gateway・スケジューラ起動前に
  `hermes cron list` で確認する**（有効なジョブが含まれ得る）。
- 競合（同名・異内容の未管理 MCP、変更済みの管理分）は勝手に上書きせず停止して差分を確認する。
- 検証時は実 `.env`・実 `9119/9120` に触れず、gateway/chat/cron を起動しない。秘密値をログに出さない。

## 手順（新規マシンへの移行）

1. **公開リポジトリを取得**:

   ```bash
   git clone <GitHub 上の ${REPO_NAME}_public リポジトリの URL>
   cd ${REPO_NAME}_public
   ```

2. **Hermes 本体を導入し default を初期設定**（既存機器ならスキップ）。
3. **手動インポート**（正本 `docs/harness_manual_import.md` の手順）:
   プラグイン 4 件（langfuse・omh・agent-importers・自作 openrouter-voice）、
   公式カタログスキル（glab 等が必要なら）、kanban 等 config 由来設定。
   Langfuse は `.env` に `HERMES_LANGFUSE_BASE_URL`／`HERMES_LANGFUSE_PUBLIC_KEY`／
   `HERMES_LANGFUSE_SECRET_KEY` を設定する。
4. **導入ツール用の仮想環境**:

   ```bash
   uv venv --python 3.13
   uv pip install -r pyproject.toml
   source .venv/bin/activate
   ```

5. **`.env` を作成**: `cp .env.EXAMPLE .env` して `HARNESS_HOME`（②のホーム）と
   `HARNESS_KANBAN_RUNS_DIR` 等の必要値を記入。使わない項目は `REPLACE_ME` のままでよい
   （必須は選択した配布物に現れるトークンだけ）。`.env` はコミットしない。
6. **dry-run**:

   ```bash
   bash install_local.sh --dry-run
   ```

   何も書き込まず、対象プロファイル・競合・置換テーブル（値はマスク表示）を確認する。
7. **apply**:

   ```bash
   bash install_local.sh --apply            # 確認プロンプトあり
   bash install_local.sh --apply --skip-confirm   # 自動実行
   ```

   内部順序: 全対象事前検証 → MCP/hooks 部分移行（default＋既存役）→ skills・SOUL・criteria 配置 →
   新規役を反映済み default から作成 → seed → 全体検証。
8. **導入後確認**:

   ```bash
   hermes profile list        # 25役が揃っているか
   hermes hooks list && hermes hooks doctor
   hermes cron list           # enabled/state を確認してから gateway を起動する
   ```

   hooks の初回承認は `hermes --accept-hooks chat` 等の TTY 実行で行う。

## 更新（既存導入先）

同じ `install_local.sh --dry-run` → `--apply` の再実行。冪等であり、無変更の統合ファイルは
書き換わらない（管理分だけが更新・廃止される）。利用者が変更した管理分があると競合停止する。

## 落とし穴

- 競合で停止したら差分を確認してから進める。再実行で解消する問題ではない。
- `.env` の `HARNESS_HOME` を間違えると別ホームへ配置する。dry-run の配置先表示を必ず確認する。
- 仮想環境を作らず PATH の python3 で実行すると PyYAML 不在で即死する。
  installer は `SRC_ROOT/.venv/bin/python3` を優先する。
- 部分移行は skills・SOUL・criteria・cron を含む installer 全体のトランザクションではない。
  統合部分（config・hooks scripts・管理情報）だけが rollback 対象。

## references

- `docs/harness_integration_migration.md` — 移行契約・競合ルール・検証
- `docs/harness_manual_import.md` — 手動導入の対象と手順
- 公開リポジトリ `README.md` — 導入手順の生成元
