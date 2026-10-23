---
name: vault_search
description: "Use when Vault内を検索して調べるとき。ヒットしたメモのパスと行番号を必ず添えて引用する。"
version: 1.1.0
author: <author>, Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Obsidian, Vault, Search, 引用]
    related_skills: [note-taking/obsidian]
---

# vault_search(Obsidian Vault 検索と引用付き回答)

Obsidian Vault を全文検索し、答えを「どのメモのどの行に書いてあったか」付きで返す手順。Vault 内を調べているときは Web 検索で代用しない。メモの作成・編集が主目的のときは note-taking/obsidian を使う。

## When to Use

- 「Vault の中を検索して」「昔のメモを探して」「あのメモに何て書いてあったっけ」と頼まれたとき
- 過去のメモの内容を引用して答えるとき(この手順なしでは引用元を言わずに答えてしまいがち)
- 使わないケース: Web の最新情報がほしいとき / メモの新規作成・編集が主目的のとき

## 手順

1. **Vault パスを確定してから file ツールに渡す**(`$VAR` は展開されないので必ず具体パスに):
   - CWD に `.obsidian/` があれば CWD が Vault(このユーザーの Vault は Dropbox/remotely-save 配下のプロジェクトディレクトリのことが多い)
   - なければ `terminal` で `printenv OBSIDIAN_VAULT_PATH` と `~/.hermes/.env` を確認
   - それも無ければ `~/Documents/Obsidian Vault`
2. **`search_files` で全文検索**する(シェルの生コマンドでの列挙・検索はしない):
   - `target: "content"`、`path: <Vault の絶対パス>`、`file_glob: "*.md"`(.obsidian 内の JSON を避ける)
   - 関連語は表記ゆれ・言い換えも含め、**1回のレスポンスで並行して複数クエリ**を投げる(例: 「カーシェア」と「タイムズ」と「月額無料」)。カタカナ語・英字名・略称も試す
   - メモ自体を探すときは `target: "files"`
   - 文脈が欲しいときは `context: 3`
3. **断片だけで意味が通るか怪しいときは `read_file` で前後を読む**
4. **下の形式でパス+行番号付き引用付きの回答をする**

## 出力形式

- 各ヒット: `<Vault 相対パス>:<行番号>` を付け、該当行を原文のまま引用する。複数行にまたがるときは `パス:開始行-終了行` の形式
- 引用(原文)の後に要約・結論を書き、どちらが原文か区別を保つ
- 0件のときは使った検索語とスコープを明示して「見つからない」と正直に言う。推測で埋めない
- ヒット件数(`total_count`)と列挙した引用の数を一致させてから答える

## Pitfalls

- **1ファイルの I/O エラー(os error 5 など)で検索全体がエラー返しになることがある**(Dropbox/remotely-save 環境)。その場合も出力にはヒットが含まれていることがある — 出力を読んでから判断し、だめなら対象フォルダを絞って再検索する
- `/mnt/c` 配下の Vault は走査が遅い。`.` のような広いパターンで全件走査しない
- パターンは正規表現として解釈される。`?` `*` `(` `[` などはエスケープ。日本語はそのまま渡してよい
- 検索語1語で 0 件 →「ない」と結論しない。表記ゆれを試してから結論する

## Verification

- 引用するパスと行番号は、search_files の出力(行番号付き)か read_file で実在を確認してから答える
- 「どのメモに書いてあったか」が回答から抜けていないか、送信前に一度チェックする
