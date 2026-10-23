# task-ambi-harness（公開版）

Hermes Agent 用ハーネス（task_ambi 4階層カンバン組織の動作環境一式）の公開配布版です。
実パス・ユーザー名・組織名・IP アドレスなどの環境固有値は、すべて `${...}` 形式の
プレースホルダ（または一般化トークン `<...>`）に置換済みです。導入時に `.env` へ実値を
設定すると、導入スクリプトが逆方向置換で実値へ復元します。

## 構成

```
distribution.yaml   配布マニフェスト（name・version・license・env_requires）
.env.EXAMPLE        導入先が埋めるべき HARNESS_* 変数の雛形（実値は書かない）
.gitignore          配布除外リスト（secrets・ランタイム状態）
SOUL.md             default プロファイルの SOUL
config.yaml         default の config（hooks・mcp_servers を含む）
mcp.json            MCP 接続定義
skills/             共有スキル一式
agent-hooks/        mermaid-check 等
souls/              25役分の SOUL.md（souls/<役名>/SOUL.md・profiles.txt と対応）
profiles.txt        25役のプロファイル名一覧
criteria/           共通 criteria.md ＋ 役別 criteria
cron/jobs.json      cron ジョブ定義（実パスはプレースホルダ化）
install_local.sh    ローカル導入スクリプト（.env 読込 → 逆方向置換 → 配置 → 25役生成 → 導入確認）
LICENSE             MIT ライセンス
README.md           本ファイル
```

## 導入手順

1. `.env.EXAMPLE` を `.env` としてコピーし、各 `REPLACE_ME` を導入先環境の実値で埋める。
   `.env` はリポジトリにコミットしないこと。
2. 単一プロファイル導入: `hermes profile install <このディレクトリ>`。
   distribution.yaml の env_requires に列挙した変数が要求される（一覧は後述の
   「env_requires 変数一覧」）。
3. 25役の再現: `hermes profile create <役名> --clone --no-alias` で default から生成し、
   `souls/<役名>/SOUL.md` で SOUL を差し替える（対象一覧は profiles.txt）。
4. 逆方向置換: 同梱の `install_local.sh` が `.env` の `HARNESS_*` キーを参照し、
   `${...}` プレースホルダを導入先の実値へ復元する（詳細は後述の
   「install_local.sh によるローカル導入」）。
5. hooks の初回承認: `--accept-hooks` 付き chat 実行か TTY 承認で allowlist に記録する。
6. 検証: `hermes profile list`（25役が揃うこと）・`hermes skills list`
   （frontmatter 破損がないこと）・`hermes hooks doctor`（mermaid-check が緑であること）。

## install_local.sh によるローカル導入

`hermes profile install` の代わりに、リポジトリ同梱の `install_local.sh` で一括導入する方法。
`.env`（`HARNESS_*` 変数）を読み込み、リポジトリ内の `${...}` プレースホルダを導入先の実値へ
逆方向置換して `HARNESS_HOME` 配下へ配置し、25役のプロファイルを
`hermes profile create --clone-from default` で生成する。

```
bash install_local.sh --dry-run              # 書き込まず配置先と置換内容を確認（値はマスク表示）
bash install_local.sh --apply                # 実配置（profile 作成を含む・確認プロンプトあり）
bash install_local.sh --apply --skip-confirm # 確認プロンプトを省略（自動実行用）
bash install_local.sh --replace-test --env FILE < input.txt > output.txt
                                             # 逆方向置換の単体テスト用（配置なし・stdin を置換して stdout へ）
```

- `HARNESS_HOME` が未設定・`REPLACE_ME`・空値のときは欠落キー一覧を表示して終了する
  （既定パスへの暗黙フォールバックはしない）。
- 置換テーブルに無い未知の `${...}` プレースホルダを検出した場合は導入を中止する。
- 既存のプロファイルがある場合は SOUL のみ差し替える。`cron/jobs.json` は既存時に `.orig` へ退避する。
- criteria は `.env` の `HARNESS_KANBAN_RUNS_DIR` 直下へ配置する。
- 参照する `HARNESS_*` キーの全容は `install_local.sh` 冒頭のコメントを参照
  （下記の env_requires 12 変数に加え、`HARNESS_USER_NAME`・`HARNESS_ORG_NAME` など
  置換テーブル分のキーを使用する。`PROJECT_*_NAME` / `ORG_NAME` / `REPO_NAME` は
  `HARNESS_PROJECT_NAME_MAP` の「一般名=実名」ペアからも供給でき、直値キーが優先される）。

### プロファイルの更新方針（重要）

`install_local.sh` が生成・更新したプロファイルは、**`hermes profile update` の対象外**である。
配布リポジトリ側の変更を導入先へ反映するには、`hermes profile update` を使わず
**本スクリプトを再実行する**（2026-10-24 人間裁定 1。根拠: ${REPO_NAME} リポジトリ
`harness_policy.md` §8 D1/D2・§9【裁定：人間】公開化・push）。

## env_requires 変数一覧

`hermes profile install` は `distribution.yaml` の `env_requires`（12 変数）に列挙した
変数を要求する。`.env.EXAMPLE` と同一の列挙であり、意味は `.env.EXAMPLE` のコメントに準じる。

| 変数 | 意味 |
|---|---|
| `HARNESS_HOME` | 導入先の Hermes ホーム（`~/.hermes` 相当）。ハーネス内の `/home/user/.hermes` 形式プレースホルダをこの値で復元する |
| `HARNESS_USER_HOME` | 導入先のユーザホーム（例: `/home/user`）。ホーム配下パスの共通接頭辞 |
| `HARNESS_VAULT_ROOT` | Obsidian vault のルートパス。vault 参照系スキル・cron ジョブ内の vault パス復元用 |
| `HARNESS_KANBAN_RUNS_DIR` | ワーク実行ルート（kanban ワーカの実行ディレクトリ） |
| `HARNESS_PROJECT_ROOT` | `${REPO_NAME}` ローカルリポジトリのパス。プロジェクト内の scripts・criteria・docs 参照の基点 |
| `HARNESS_LANGFUSE_URL` | Langfuse の URL（self-host 環境のホスト名または IP+ポート） |
| `HARNESS_LANGFUSE_PUBLIC_KEY` | Langfuse の public key（プロジェクト設定で発行） |
| `HARNESS_LANGFUSE_SECRET_KEY` | Langfuse の secret key（秘匿値のため取り扱い注意） |
| `HARNESS_PROJECT_NAME_MAP` | プロジェクト一般名と実名の対応（criteria 一般化の復元用）。カンマ区切りの「一般名=実名」ペア（例: `g01=REPLACE_ME,p01=REPLACE_ME`） |
| `HARNESS_DASHBOARD_BASIC_AUTH_USERNAME` | ダッシュボード basic auth のユーザ名 |
| `HARNESS_DASHBOARD_BASIC_AUTH_PASSWORD_HASH` | ダッシュボード basic auth の scrypt パスワードハッシュ（秘匿値のため取り扱い注意） |
| `HARNESS_DASHBOARD_BASIC_AUTH_SECRET` | ダッシュボード basic auth の secret トークン（秘匿値のため取り扱い注意） |

秘匿値に分類されるのは `HARNESS_LANGFUSE_SECRET_KEY`・`HARNESS_DASHBOARD_BASIC_AUTH_PASSWORD_HASH`・
`HARNESS_DASHBOARD_BASIC_AUTH_SECRET` の 3 変数。実値は `.env`（配布対象外・コミット禁止）にのみ置く。

## cron の再設定（重要）

- `cron/jobs.json` を配置しても、ジョブは**自動スケジュールされない**（公式仕様）。
  配布しても導入先で自動的に動き始めることはない。
- 導入後、`hermes cron list` でジョブを確認し、必要なジョブを `hermes cron enable <job-id>`
  で個別に有効化する（全ジョブを一斉に有効化しないこと）。
- 有効化後、`hermes cron doctor` でスキル解決・配信ターゲットのエラーを確認する。
- cron ジョブが `script:` でスクリプトを参照する場合は、参照先スクリプトを
  `$HERMES_HOME/scripts/` へ**手動でコピー**する。

## 注意事項

- `chrome-devtools-win` は Windows 機器専用（cmd.exe 経由で Windows 側 Chrome を操作）。
  Windows 以外の導入先では config.yaml・mcp.json の当該エントリを無効化するか除去する。
- `memories/`・`auth.json`・`.env` は配布対象外。導入先ごとに用意する。
- 一般化トークン（`<...>` 形式）は復元対象外の説明文・著者表記上の置換である。

## ライセンス

MIT License（`LICENSE` を参照）。
