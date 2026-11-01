---
name: taskambi_sdd-setup
description: "Use when SDD をリポジトリにセットアップするとき。対象確認・前提検査・ガード生成を行う。"
version: 1.0.0
---

# sdd-setup(SDD プロジェクト別セットアップ)

**作業場所は WSL 側のローカルリポジトリ。** `/mnt/` で始まるパス(Windows 側)を作業場所にしない。`specify init` も speckit コマンドの実行も WSL 側でだけ行う。

## When to Use

人間が「SDD をこのリポジトリにセットアップして」「SDD を使えるようにして」など、特定のプロジェクトで speckit 自律実行を始める準備を求めたとき。スキル群(sdd-project-lead / sdd-pipeline / sdd-worker-rules)はプロジェクト非依存で、プロジェクト固有の値はこのセットアップが各リポジトリの `.hermes/sdd-guard.toml` に生成する。

## Procedure

### 1. 対象リポジトリの明示確認

**起動時に必ず人間へ確認する**(clarify)。引数や前文でパスが示されていても、そのパスでよいかを明示的に確認する。勝手に推定して進めない。

### 2. 前提チェック(読み取り専用)

プロジェクト側:
- `git rev-parse --show-toplevel` が `/mnt/` で始まらないこと。リモートが GitLab であること(想定と違えば報告)
- 作業ツリーがクリーンであること。未コミット変更があれば人間にコミットを依頼して停止
- specify CLI の版(`specify version`)と `.specify/` の雛形の版(`.specify/init-options.json` や `specify integration status`)が一致していること
- hermes 統合がインストール済みであること(`specify integration status` が OK で default/installed に hermes がある)。無ければ人間に `specify integration install hermes --force` を提示して停止(自分ではインストールしない。人間の明示指示があれば実行してよい)
- 憲章 `.specify/memory/constitution.md` と基本設計(既定は `docs/design/`。無ければ場所を人間に尋ねる)があること
- Windows 側の Obsidian フォルダに `.specify/` や `specs/` が誤って作られていないか(見つけても削除せず報告)

グローバル側(報告のみ。変更する場合は人間の承認を得る):
- `~/.hermes/skills/speckit-*`(8コマンド分以上)があること
- 各役割プロファイル(planner / system_engineer / architect / code_reviewer / programmer / debugger / test_engineer)の `skills.external_dirs` に `${HERMES_HOME}/skills` があること(`HERMES_HOME=<プロファイルのホーム> hermes config get skills.external_dirs` で確認)
- `kanban.max_in_progress`(1 推奨)と `kanban.auto_decompose`(false 推奨)の現在値
- `kanban.review_dispatch` が true であること(二重ゲート=作業役の request_review を SE が自動検収する仕組みの前提。既定プロファイルと役割プロファイルの config を確認)

### 3. RED_PATHS / YELLOW_PATHS の提案と人間の確認

構成を見て案を作り、clarify で人間の確認を得てから使う。初期案:
- RED(変更されたら即停止): 基本設計(`docs/design/**`)・`.specify/**`(ただし `feature.json` は除外)・依存と静的検査の設定(`pyproject.toml` / `uv.lock` / `.importlinter` 等)・CI 設定(`.gitlab-ci.yml` 等)・エージェント向け約束事(`CLAUDE.md` / `AGENTS.md` / `.roo/**` 等、存在するもの)・`.hermes/**`
- YELLOW(追加のみ可): 共通インタフェース・共通ライブラリ・composition root に相当する場所(憲章とディレクトリ構成から特定する)

### 4. ガード設定の生成と検証

1. `<対象リポジトリ>/.hermes/sdd-guard.toml` を作成する(確認済みの RED/YELLOW を glob で書く。このファイル自体も `.hermes/**` で RED に含まれる)
2. `uv run python ${HERMES_HOME}/skills/sdd-worker-rules/scripts/guard_check.py --init-baseline` を実行する(gitignore された RED パスのハッシュベースラインを作成)
3. 同スクリプトを通常実行し、`ok: true` を確認する

### 5. 人間への引き渡し

- `.hermes/sdd-guard.toml` とベースラインをコミットするよう依頼する(コミットは人間の作業)
- 開始コマンドを提示する:

```bash
hermes kanban create "[P] <名前> 計画" \
  --assignee planner \
  --workspace dir:<WSL側リポジトリの絶対パス> \
  --skill sdd-project-lead \
  --body "<目的・対象の feature・基本設計の参照節。試験なら試験範囲>"
```

監視: `hermes kanban watch` / 人間への回覧への回答: `hermes kanban comment <id> "<回答>"` のあと `hermes kanban unblock <id>`。

## Pitfalls

- `specify init --force` / `specify integration uninstall` / `specify integration switch` は人間の明示指示なしに実行しない(uninstall はグローバルの `speckit-*` スキルも消す仕様)
- Spec Kit 公式スキル(`speckit-*`)の中身を編集しない。新しく作るスキルの名前を `speckit-` で始めない
- パッケージの追加が必要になっても勝手に `uv add` しない。提案して止まる
- Python は `uv run` で実行し、実行前に対象リポジトリの pyproject.toml を読む
- Markdown のタイトルに Obsidian 禁止文字(`< > : " / \ | ? *`)を使わない
- 前提と実際の仕様が食い違う場合は、自分で辻褄を合わせず食い違いとして報告する

## Verification

- `specify integration status` が OK であること
- `guard_check.py` が `ok: true` を返すこと
- ガード設定とベースラインが人間によってコミットされたこと(`git status` がクリーン)
