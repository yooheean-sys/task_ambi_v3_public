---
name: vault_custom_scripts
description: ${REPO_NAME} scripts 配下のスクリプト実行用。失敗時は意図どおり成功するよう都度修正する。
version: 1.0
author: ${USER_NAME_LOWER}
license: private
metadata:
  hermes:
    tags: [task_ambi, uv, scripts]
---

# vault_custom_scripts — ${REPO_NAME} の scripts 実行

## When to Use
- `${REPO_ROOT}` の `scripts/` 配下のスクリプトを実行するとき
- 実行に失敗したときは、ユーザーの実行意図どおりに成功するようスクリプトを都度修正してよい（ユーザー指示）

## 前提（役割分担）
- **プログラムの所在（実行環境）**: ローカルリポジトリ `${REPO_ROOT}`
- **走査・操作の対象データは Obsidian vault**: `${VAULT_ROOT}`。各スクリプトは vault 内のデータを読み・書きするため、対象ディレクトリ（入力フォルダ・`--root` 等）は vault 内のディレクトリを指定する
- vault のパスは日本語（`アプリ`）を含むため、シェルには必ずクォートで渡す
- vault は Dropbox 同期（remotely-save）下にあるため、書き込み・削除は同期先にも伝播する
- Python 3.13（`.python-version`）+ uv。`.venv` が無くても `uv run` が自動生成する
- `pyproject.toml` の dependencies は空。スクリプト固有の依存は下記のとおり実行時に渡す
- scripts/ はコミット済み（2026-10-17、e7c61b4）。以後の修正・追加ファイルはコミット可否をユーザーに確認する

## 実行手順
1. `cd ${REPO_ROOT}` してから実行する
2. まず `ls scripts/` で最新の一覧を確認する（スクリプトは随時追加される想定）。未記載のスクリプトは冒頭 docstring を読んで引数仕様・依存を把握してから実行する
3. 以下の対応表に従って実行する

## スクリプト対応表（2026-10-17 実行検証済み）

### clear_archives.py — `_archive` フォルダの中身を空にする
- 標準ライブラリのみ。`uv run scripts/clear_archives.py`
- **デフォルトはドライラン**。実際に削除するには `--execute` を付け、対話確認プロンプトを避けるため `--yes` も必須:
  `uv run scripts/clear_archives.py --root '<vault内の掃除したいディレクトリ>' --execute --yes`
- **対象ルートは vault 内のディレクトリを `--root` で明示指定**する（既定はスクリプト配置基準＝リポジトリ自身。指定しないと vault ではなくリポジトリを走査する）
- 主な引数: `--root`、`--name`（既定 `_archive`）、`--skip`、`--verbose`
- **危険操作**: 削除はゴミ箱を経由しない完全削除で、vault 対象なら Dropbox 同期先にも伝播する。vault への `--execute` 実行は必ずユーザーの明示承認を取る

### markdown_to_xlsx.py — Obsidian マニュアルノート群 → xlsx 変換
- 依存 openpyxl / Pillow が pyproject に無いため `--with` で渡す（実行検証済み。openpyxl 3.1.5 / pillow 13.0.0 で動作確認）:
  `uv run --with openpyxl --with pillow scripts/markdown_to_xlsx.py '<vault内の入力フォルダ>' '<出力xlsx>' [--attachments-dir DIR]`
- **入力フォルダは vault 内のマニュアルノート群のルート**（1サブフォルダ = 1業務カテゴリ = 1シート）。走査は直下＋そのサブフォルダの1階層のみ（孫以下は再帰しない）
- 画像参照があると、解決の最終手段として入力フォルダ全体の再帰検索（rglob）が走る。大きなフォルダを指定するとそこが重くなる
- **出力 xlsx は新規 Workbook から作成される**（2026-10-17 実装確認済み）。出力先に既存 xlsx があると**ファイル全体が上書きされ、他シートも消える**（docstring の「同名シートを置換」は同一実行内の名前衝突時のみ有効）。既存ファイルを残したい場合は出力先をユーザーに確認する
- 入力フォルダ直下にもサブフォルダにも md が無いと exit 1
- 既知の制約: 画像はフローティング配置のためセル値として読めない（人間用のビュー用）

### prompts_snipetter.py — Obsidian プロンプトノート → Espanso match 定義
- PEP 723 インライン依存（python-frontmatter, pyyaml）なので `uv run --script scripts/prompts_snipetter.py` で自動解決される
- WSL 対応済み（2026-10-17 修正・検証済み）: WSL 実行時は Windows 側ホーム（/mnt/c/Users/<user>）を自動検出し、書き出し先を Windows espanso の match ディレクトリ（`/mnt/c${USER_HOME_MAC}/AppData/Roaming/espanso/match/obsidian_prompts.yml`）に向ける。Windows で直接実行した場合は従来どおり home 基準 + `espanso path config` 優先
- 対象は vault 内の `templates/prompts`（`${VAULT_ROOT}/templates/prompts`）で、frontmatter に `espanso: true` と `trigger` を持つノート。WSL 実行時は Windows 側の Dropbox 同期 vault を自動解決する（2026-10-17 vault 対象に修正済み、23 件書き出しを検証）
- **反映は手動**: 書き出し後、Windows 側で `espanso restart` を実行する必要がある（WSL からは実行できない）

## 失敗時の修正方針
- 実行に失敗したら、実行の意図どおりに成功するよう `scripts/` 配下のプログラムを都度修正してよい
- 修正前に失敗メッセージを記録し、修正後に再実行して成功を確認する。修正内容はユーザーに報告する
- `--with` で済む依存は pyproject に勝手に追加せず、恒常用するなら `uv add` の提案のみする
- 修正したスクリプトのコミット可否はユーザーに確認する
