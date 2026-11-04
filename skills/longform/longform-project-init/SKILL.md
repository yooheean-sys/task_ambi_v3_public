---
name: longform-project-init
author: Hermes Agent
license: MIT
description: "Use when scaffolding a new long-form Quarto writing repo."
version: 1.0.0
metadata:
  hermes:
    tags: [writing, quarto, scaffold]
    parent: longform-writing-pipeline
---

# longform-project-init(執筆リポジトリの雛形生成)

longform-writing-pipeline の3層構造(仕様/原稿/検証)に沿った執筆リポジトリを作る。文書は書かない。markdown→docx 変換は対象外。

## When to Use
- 新しい論文・報告書・明細書プロジェクトを始めるとき
- 既存 repo に検証ゲート(justfile+scripts)を後付けするとき

## 手順
1. **配置を決める**: 既定は `~/project/<name>`(WSL側FS・高速)。Obsidian vault 配下も可だが node_modules・レンダ出力(_site)は vault に置かない(Dropbox 同期が破綻する)。パスは必ず絶対パスで扱う。
2. **雛形を取得する**: 本 skill ディレクトリ(skill_view の返す path)の `templates/scaffold.md` に全ファイルの中身がある。`scripts/check_refs.py` と `scripts/coverage.py` を repo の `scripts/` にコピーする。
3. **ファイルを作成する**: scaffold.md の構成に従い write_file で作る。ファイル名に Obsidian 禁止文字(< > : " / \ | ? *)を使わない。
4. **ツール導入を確認する**: quarto は必須(`quarto --version`)。textlint は repo 外のツールディレクトリ(既定 `~/.hermes/tools/textlint`)に `npm install --prefix <dir> textlint textlint-rule-preset-ja-technical-writing textlint-rule-prh @textlint-ja/textlint-rule-preset-ai-writing` で導入する。node 無し・textlint 無しの場合は just lint が SKIP になる。ユーザーに SKIP を明示する。vale は任意(英語文書がある場合)。
5. **動作確認する**: `just lint`(SKIP許容)→ `just check-refs`(bib 空なら警告のみ)→ `just coverage`(outline 未作成なら FAIL メッセージで正常)→ `just build-html`(main.qmd 雛形が render できる)。全て終了コードを確認する。
6. **git 初期化する**: git init + 初回 commit。push はユーザー手動(WSL に認証経路なし)。

## Pitfalls
- node_modules と _site を vault に置かない。repo は軽量に保ち、ツールは repo 外のツールディレクトリへ。
- just が未導入なら各ターゲットの中身のコマンドを直接実行する(対応表は templates/scaffold.md 冒頭)。
- `--to pdf` は LaTeX エンジンが要る。未導入なら html のみで進める。

## References
- `templates/scaffold.md` — 全ファイル雛形と just ターゲット対応表
- `scripts/check_refs.py` — 引用ゲート本体
- `scripts/coverage.py` — カバレッジ・整合ゲート本体
