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
skills.txt          配布対象スキルの相対パス許可リスト
skill_manifest.py   許可リストの共通検証処理（Python 標準ライブラリのみ）
skills/             skills.txt に登録したスキルと同梱ファイル
agent-hooks/        mermaid-check 等
souls/              25役分の SOUL.md（souls/<役名>/SOUL.md・profiles.txt と対応）
profiles.txt        25役のプロファイル名一覧
criteria/           共通 criteria.md ＋ 役別 criteria
cron/jobs.json      cron ジョブ定義（実パスはプレースホルダ化）
install_local.sh    ローカル導入スクリプト（.env 読込 → 逆方向置換 → 配置 → 25役生成 → 導入確認）
LICENSE             MIT ライセンス
README.md           本ファイル
```

## スキルの配布対象

スキルは `skills.txt` に事前登録したものだけを配布・導入する。1行に1スキル、
`skills/` を基準とする相対ディレクトリを書く。たとえば次の内容なら2件だけが対象になる。

```text
vault/vault_custom_scripts
pbi
```

- 正本では `harness/skills.txt` を編集する。対応する実体は `harness/skills/` に置く。
- 各登録先に `SKILL.md` が必要。同じディレクトリ内の references・scripts・assets も対象。
  カテゴリの説明書など、登録したスキルディレクトリの外にあるファイルは配布しない。
- 空行と `#` から始まるコメント行は無視する。行の前後の空白は取り除く。
- ワイルドカード・絶対パス・親ディレクトリ参照・重複・シンボリックリンクは許可しない。
- リスト未作成・登録先の欠落・不正な指定は生成や導入の書き込み前にエラーとなる。
  空のリストは「スキルを配布しない」の意味であり、全件コピーには戻らない。
- 依存スキルは自動追加しない。必要なものを個別に登録する。
- 既存配布対象を初期登録しているが、その後スキルを増やしても自動では登録されない。
- 導入先の未登録スキルは削除しない。リストから外したスキルを公開版から除くには、
  正本側でリストを変更して再生成する。
- 公開側のリストとディレクトリ名には同じ公開用置換が適用される。

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
`.env`（`HARNESS_*` キー）を読み込み、リポジトリ内の `${...}` プレースホルダを導入先の
実値へ逆方向置換して配置する（skills・SOUL・criteria・cron・agent-hooks を含む）。

```
bash install_local.sh --dry-run              # 書き込まず配置先と置換内容を確認
bash install_local.sh --apply                # 実配置（profile 作成を含む）
bash install_local.sh --apply --skip-confirm # 確認プロンプトを省略（自動化用）
bash install_local.sh --replace-test --env FILE < input.txt > output.txt
                             # 逆方向置換の単体テスト（配置なし・stdin を置換して stdout へ）
```

- `.env` が無い場合は `.env.EXAMPLE` をコピーして記入を案内して終了する。
- 直値キー（`HARNESS_PROJECT_*_NAME` 等）が優先され、`HARNESS_PROJECT_NAME_MAP`
  （一般名=実名ペア）は欠落キーの供給に使われる。
- criteria は `${KANBAN_RUNS_DIR}`（`HARNESS_KANBAN_RUNS_DIR`）直下へ配置する。

### プロファイルの更新方針（重要）

`install_local.sh` で作成したプロファイルは `hermes profile update` の対象外である
（distribution 管理外のため）。更新は本リポジトリの `install_local.sh --apply` の再実行で
行う（2026-10-24 人間裁定 1・根拠: ${REPO_NAME} リポジトリ）。

## env_requires 変数一覧

`distribution.yaml` の `env_requires` に列挙した 12 変数（`.env.EXAMPLE` と同一）。

| 変数 | 意味 |
|---|---|
| `HARNESS_HOME` | 導入先の Hermes ホーム（`~/.hermes` 相当） |
| `HARNESS_USER_HOME` | ユーザホーム（例: `/home/user`） |
| `HARNESS_VAULT_ROOT` | Obsidian vault のルートパス |
| `HARNESS_KANBAN_RUNS_DIR` | kanbanRuns の配置先（criteria もここへ置く） |
| `HARNESS_PROJECT_ROOT` | task_ambi プロジェクトのルートパス |
| `HARNESS_LANGFUSE_URL` | Langfuse エンドポイント URL |
| `HARNESS_LANGFUSE_PUBLIC_KEY` | Langfuse の公開鍵 |
| `HARNESS_LANGFUSE_SECRET_KEY` | Langfuse の秘密鍵 |
| `HARNESS_USER_NAME` | 導入先ユーザ名 |
| `HARNESS_USER_NAME_LOWER` | 同上の小文字形（パス用） |
| `HARNESS_ORG_ROOT` | 組織ルートパス（`/home/user/<org>` 等） |
| `HARNESS_ORG_NAME` | 組織名 |

## cron の再設定（重要）

- `cron/jobs.json` を配置しても、ジョブは**自動スケジュールされない**（公式仕様）。
- 導入後、`hermes cron list` でジョブを確認し、必要なジョブを `hermes cron enable <job-id>`
  で個別に有効化する（全ジョブを一斉に有効化しないこと）。
- 有効化後、`hermes cron doctor` でスキル解決・配信ターゲットのエラーを確認する。

## 注意事項

- `chrome-devtools-win` は Windows 機器専用（cmd.exe 経由で Windows 側 Chrome を操作）。
  Windows 以外の導入先では config.yaml・mcp.json の当該エントリを無効化するか除去する。
- `memories/`・`auth.json`・`.env` は配布対象外。導入先ごとに用意する。
- 一般化トークン（`<...>` 形式）は復元対象外の説明文・著者表記上の置換である。

## ライセンス

MIT License（`LICENSE` を参照）。
