---
name: create-pbi
description: PBIを起票するとき。grilling対話→PBI整形→glabでGitLab起票まで。
version: 1.0
author: ${USER_NAME_LOWER}
license: private
metadata:
  hermes:
    tags: [pbi, gitlab, glab, backlog]
---

# PBI 起票

## When to Use
- メモ書き・アイデアを PBI（Product Backlog Item）として起票するとき
- 「PBIにして」「バックログに起票して」等の依頼

## Workflow

1. **grilling で対話決定（必須・最初の工程）**
   - `skill_view(name='grilling')` をロードし、その手順に従ってユーザーと対話する。
   - 質問は 1 個ずつ、必ず推奨案を付けて提示する（clarify で「選択肢＋推奨」をセットに）。
   - 決める項目: 対象リポジトリ / タイトル / 概要 / 提供価値 / 受け入れ条件 / スコープ外事項 / 付録に追い出す内容。
   - コードベースやリポジトリで答えられる質問は自ら調べて答え、ユーザーに聞かない。
2. **PBI 整形**
   - 下記テンプレート（espanso `;pbi` スニペットと同一）に従い markdown を書く。
   - 本体は簡潔に（各節 1〜3 行目安）。書ききれない内容は付録メモへ追い出す。
   - タイトル・ファイル名に Obsidian 禁止文字（< > : " / \\ | ? *）を使わない。
3. **ファイル書き出し**
   - `write_file` で `pbi_<slug>.md` を作成し、応答に `MEDIA:/絶対パス` を書いてダウンロード可能にする。
   - ファイル構成: PBI 本体 → `---` 区切り → 付録メモ（付録が無ければ省略）。
4. **GitLab 起票（実行前に必ず承認を取る）**
   - 起票内容（タイトル・ファイルの要点）を提示し、clarify で実行可否を確認してから実行する。
   ```bash
   glab issue create -R <owner>/<repo> --title "<タイトル>" --description "$(cat pbi_<slug>.md)"
   ```
   - 既定リポジトリ: task_ambi 関連は `${ORG_NAME}/${REPO_NAME}.0`
   - description は GitLab markdown として解釈される。付録メモは `<details><summary>付録メモ</summary>…</details>` で折りたたむと本文が読みやすい。
5. **検証と報告**
   - `glab issue view <iid> -R <repo>` で起票内容を確認し、issue URL をユーザーへ報告する。

## PBI テンプレート（espanso `;pbi` と同一）

```markdown
### ●タイトル
- 

### ●概要
- 

### ●説明
- 

### ●提供する価値（なぜ必要か）
- 

### ●受け入れ条件（このバックログが完了したとみなすための条件）
- 

### ●その他考えられる実装案
- 

### ●良い点と悪い点
- **良い点**:
- **悪い点**:

### ●要検討事項
- 
```

## 注意
- glab 1.36.0 の `issue create` 成功時の出力は `/-/work_items/<iid>` 形式のURL（issues と同物）。`issue view`/`issue close` には数値の iid を使う。
- glab はインストール済み・${GITLAB_HOST} に `<gitlab-user>` としてログイン済み（2026-10-17 検証）。
- `glab auth status` の末尾に `! Invalid token provided` と出ることがあるが、`glab issue list` 等の実行が成功していれば実害なし。起票前に `glab issue list -R <repo>` を1回実行して動作確認するのが確実。
- 起票は外部副作用。ユーザー承認なしに `glab issue create` を実行しない。タイムアウト・エラー時は勝手に再実行せず状況を報告して待つ。
