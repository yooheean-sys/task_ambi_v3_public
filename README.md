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
LICENSE             MIT ライセンス
README.md           本ファイル
```

## 導入手順

1. `.env.EXAMPLE` を `.env` としてコピーし、各 `REPLACE_ME` を導入先環境の実値で埋める。
   `.env` はリポジトリにコミットしないこと。
2. 単一プロファイル導入: `hermes profile install <このディレクトリ>`。
   distribution.yaml の env_requires に列挙した変数が要求される。
3. 25役の再現: `hermes profile create <役名> --clone --no-alias` で default から生成し、
   `souls/<役名>/SOUL.md` で SOUL を差し替える（対象一覧は profiles.txt）。
4. 逆方向置換: 導入スクリプト（install_local.sh・別途提供）が `.env` の `HARNESS_*`
   キーを参照し、`${...}` プレースホルダを導入先の実値へ復元する。
5. hooks の初回承認: `--accept-hooks` 付き chat 実行か TTY 承認で allowlist に記録する。
6. 検証: `hermes profile list`（25役が揃うこと）・`hermes skills list`
   （frontmatter 破損がないこと）・`hermes hooks doctor`（mermaid-check が緑であること）。

## cron の再設定（重要）

- `cron/jobs.json` を配置しても、ジョブは**自動スケジュールされない**（公式仕様）。
- 導入後、`hermes cron list` でジョブを確認し、必要なジョブを導入先で明示的に有効化する。
- 有効化後、`hermes cron doctor` でスキル解決・配信ターゲットのエラーを確認する。

## 注意事項

- `chrome-devtools-win` は Windows 機器専用（cmd.exe 経由で Windows 側 Chrome を操作）。
  Windows 以外の導入先では config.yaml・mcp.json の当該エントリを無効化するか除去する。
- `memories/`・`auth.json`・`.env` は配布対象外。導入先ごとに用意する。
- 一般化トークン（`<...>` 形式）は復元対象外の説明文・著者表記上の置換である。

## ライセンス

MIT License（`LICENSE` を参照）。
