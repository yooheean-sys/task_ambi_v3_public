# task-ambi-harness（公開版）

Hermes Agent 用ハーネス（task_ambi 4階層カンバン組織の役割・スキル・MCP・hooks）の公開配布版です。
`config.yaml` 全体は配布しません。導入先の初期設定済み config の `mcp_servers` と `hooks`
だけを部分更新し、モデル・認証・プラグインなどの既存設定は維持します。
実パス・ユーザー名・組織名・IP アドレスなどの環境固有値は、すべて `${...}` 形式の
プレースホルダ（または一般化トークン `<...>`）に置換済みです。導入時に `.env` へ実値を
設定すると、導入スクリプトが逆方向置換で実値へ復元します。

## 構成

```
distribution.yaml   配布マニフェスト（name・version・license・env_requires）
.env.EXAMPLE        導入先が埋めるべき HARNESS_* 変数の雛形（実値は書かない）
.gitignore          配布除外リスト（secrets・ランタイム状態）
SOUL.md             default プロファイルの SOUL
mcp.json            MCP 接続定義の正本（Serena を含む）
hooks.json          shell hooks 登録定義の正本
integration_settings.py  既存設定の部分移行・競合検知・復元
pyproject.toml      導入ツールの依存定義（Python・PyYAML）
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

1. Hermes 本体を導入し、導入先 default の初期設定を済ませる。既存 `config.yaml` が
   ない場合は停止する。Langfuse 等のプラグインと認証は導入先で手動設定する。
2. 本ディレクトリで導入ツール用の仮想環境を準備する。

   ```bash
   uv venv --python 3.13
   uv pip install -r pyproject.toml
   source .venv/bin/activate
   ```

3. `.env.EXAMPLE` を `.env` としてコピーし、必要な `HARNESS_*` を記入する。
   `.env` はコミットしない。未使用の項目は `REPLACE_ME` のままでよい。
4. `bash install_local.sh --dry-run` で対象・競合を確認後、`--apply` で導入する。
5. 導入先で MCP 依存コマンドと hooks の初回承認を確認する。installer は MCP サーバー・
   gateway・chat・cron を起動せず、hooks を一括自動承認しない。

`hermes profile install` 単体では、専用データからの部分設定反映や25役の再現は完了しない。
完全な導入と更新の入口は `install_local.sh` に統一する。

## install_local.sh によるローカル導入

リポジトリ同梱の `install_local.sh` で導入・更新する。
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

### MCPとhooksの部分移行

- `mcp.json` の `mcpServers` を実行時 config の `mcp_servers` に登録する。
  `hooks.json` の `hooks` をイベント別に統合する。配布物の `config.yaml` は読み込まない。
- 無関係な既存 MCP・hooks・モデル・MoA・Gateway・認証・plugins は保持する。
- default と `profiles.txt` に対応する既存役を事前検証し、競合時は他の配布物の配置前に停止する。
  対象外のプロファイルには触れない。新規役は更新済み default から作成する。
- 同一内容は再利用する。同名・異内容の未管理 MCP や、変更済みの管理対象は勝手に上書きしない。
- 管理情報は各ホームの `local/` に記録する。ハーネスが追加した登録・scripts だけを
  更新・廃止時の削除対象とし、初回から同じ内容で存在した利用者所有の項目は所有権を奪わない。
- 設定と scripts の部分移行はバックアップ・ロック・変更検知付きで反映する。
  途中失敗時はこの処理が変更した範囲を復元する。skills・SOUL・criteria・cron を含む
  installer 全体のトランザクションではない。
- 秘密の環境変数参照を実値へ展開して保存しない。CLI の設定値・反映コマンドをログに出さない。
- 既に旧版で全体移行した環境のモデル・plugins 等を元に戻す処理ではない。

### プロファイルの更新方針（重要）

`install_local.sh` で作成したプロファイルは `hermes profile update` の対象外である
（distribution 管理外のため）。更新は本リポジトリの `install_local.sh --apply` の再実行で
行う（2026-10-24 人間裁定 1・根拠: ${REPO_NAME} リポジトリ）。

## env_requires 変数一覧

`distribution.yaml` は基本的な環境変数を宣言する。専用 installer は
`HARNESS_HOME`・`HARNESS_KANBAN_RUNS_DIR` と、選択した配布物で使用する値だけを要求する。
供給可能なキーの一覧は `.env.EXAMPLE` に記載する。Langfuse・dashboard の認証値は要求しない。

| 変数 | 意味 |
|---|---|
| `HARNESS_HOME` | 導入先の Hermes ホーム（`~/.hermes` 相当） |
| `HARNESS_USER_HOME` | ユーザホーム（例: `/home/user`） |
| `HARNESS_VAULT_ROOT` | Obsidian vault のルートパス |
| `HARNESS_KANBAN_RUNS_DIR` | kanbanRuns の配置先（criteria もここへ置く） |
| `HARNESS_PROJECT_ROOT` | task_ambi プロジェクトのルートパス |
| `HARNESS_PROJECT_NAME_MAP` | 一般名と正式名の対応。直値キーでの指定も可能 |
| `HARNESS_USER_NAME` | 導入先ユーザ名 |
| `HARNESS_USER_NAME_LOWER` | 同上の小文字形（パス用） |
| `HARNESS_ORG_ROOT` | 組織ルートパス（`/home/user/<org>` 等） |
| `HARNESS_ORG_NAME` | 組織名 |

## cron の再設定（重要）

- cron は設定部分移行とは別の既存配布対象。`cron/jobs.json` は配置するが、配布 JSON の
  `enabled/state` を無効化する処理はない。有効な定義が含まれ得る。
- gateway・スケジューラを起動する前に、導入先でジョブと配信先を確認する。
  公式 distribution の cron マージ・停止方針を、この専用 installer に当てはめない。

## 注意事項

- `chrome-devtools-win` は Windows 機器専用（cmd.exe 経由で Windows 側 Chrome を操作）。
  Windows 以外の導入先では、正本 `mcp.json` の当該エントリを無効化するか除去する。
- `memories/`・`auth.json`・`.env` は配布対象外。導入先ごとに用意する。
- 一般化トークン（`<...>` 形式）は復元対象外の説明文・著者表記上の置換である。

## ライセンス

MIT License（`LICENSE` を参照）。
