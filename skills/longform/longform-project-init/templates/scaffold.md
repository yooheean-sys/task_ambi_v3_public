# scaffold templates — longform 執筆リポジトリ雛形

全ファイルをここから write_file する。`<name>`/`<TITLE>` は置換。 Obsidian 禁止文字は使わない。

## 配置

```
<name>/
  _quarto.yml
  manuscript/
    main.md
    01_intro.md
  refs/
    references.bib
  spec/
    outline.md
    glossary.md
    notation.md
    style.md
  scripts/
    check_refs.py   # 本skillの scripts/ からコピー
    coverage.py     # 同上
  justfile
  .textlintrc
  prh.yml
  .gitignore
  README.md
```

## just ターゲット対応表(just 未導入時に直接実行)

| target | コマンド |
|---|---|
| lint | `sh scripts/lint.sh`(textlint ラッパー。valeは任意) |
| check-refs | `python3 scripts/check_refs.py` |
| coverage | `python3 scripts/coverage.py` |
| build-html | `quarto render manuscript/main.md --to html` |
| build | 上記+`--to pdf`(LaTeX 要) |
| diff | `git diff --stat`(+pandiff 任意) |

## _quarto.yml

```yaml
project:
  type: default
  output-dir: _site
format:
  html:
    toc: true
    number-sections: true
    lang: ja
  # pdf:
  #   documentclass: ltjsarticle   # PDF用。TeX Live 導入時に有効化
```

## manuscript/main.md(マニフェスト)

```markdown
---
title: "<TITLE>"
lang: ja
bibliography: ../refs/references.bib
---

{{< include 01_intro.md >}}
{{< include 02_method.md >}}

## 参考文献 {#sec-refs}

::: {#refs}
:::
```

include 行は outline の sections に合わせて並べる(マニフェスト駆動)。

## manuscript/01_intro.md(空節スタブ)

```markdown
# <SECTION TITLE> {#sec-<id>}

<!-- TODO: longform-section-draft で起草 -->
```

## refs/references.bib(スタブ)

```bibtex
% 実在確認済みの項目のみ。longform-outline が登録する。
```

## spec/outline.md(スタブ)

`````markdown
# Outline — <TITLE>

## 目的

(自由記述: 目的・読者・分量)

## 構造

```yaml
title: "<TITLE>"
doc_type: report
approved: false
sections: []
```
`````

## spec/glossary.md(スタブ)

```markdown
# Glossary

| 正用語 | 禁止表記(カンマ区切り) |
|---|---|
| Quarto | クオルト,quarto |
```

## spec/notation.md(スタブ)

```markdown
# Notation

| 記号・符号 | 意味 |
|---|---|
```

## spec/style.md(スタブ)

```markdown
# Style

- である調で統一する(textlint 設定と一致させる)
- 1文1行で書く(diff 規約)
```

## justfile

```just
TOOLDIR := env_var_or_default("TEXTLINT_TOOLDIR", env_var_or_default("HOME", "${USER_HOME}") + "/.hermes/tools/textlint")
PY := "python3"

default:
    @just --list

lint:
    if [ -x "{{TOOLDIR}}/node_modules/.bin/textlint" ]; then
      sh scripts/lint.sh
    else
      echo "SKIP: textlint 未導入 (npm install --prefix {{TOOLDIR}} textlint textlint-rule-preset-ja-technical-writing textlint-rule-prh @textlint-ja/textlint-rule-preset-ai-writing textlint-filter-rule-comments textlint-plugin-markdown)"
    fi
    if command -v vale >/dev/null 2>&1; then
      vale manuscript/ || true
    else
      echo "SKIP: vale 未導入"
    fi

check-refs:
    {{PY}} scripts/check_refs.py

coverage:
    {{PY}} scripts/coverage.py

build-html:
    quarto render manuscript/main.md --to html

build:
    quarto render manuscript/main.md --to html
    quarto render manuscript/main.md --to pdf

diff:
    #!/usr/bin/env sh
    git diff --stat || true
    if command -v pandiff >/dev/null 2>&1; then
      echo "pandiff 利用可"
    else
      echo "SKIP: pandiff 未導入 (要 pandoc)"
    fi
```

## .textlintrc

```json
{
  "filters": { "comments": true },
  "rules": {
    "preset-ja-technical-writing": {
      "sentence-length": { "max": 150 },
      "max-ten": { "max": 5 },
      "no-mix-dearu-desumasu": false
    },
    "prh": { "rulePaths": ["./prh.yml"] },
    "@textlint-ja/preset-ai-writing": true
  }
}
```

## scripts/lint.sh(雛形は本skillの scripts/ には無い。repo に手で置くか下記を使用)

```sh
#!/usr/bin/env sh
# textlint: .md を直接対象にする(拡張子統一によりラッパ不要)
TL="${TEXTLINT_TOOLDIR:-$HOME/.hermes/tools/textlint}/node_modules/.bin/textlint"
cd "$(dirname "$0")/.."
if [ -x "$TL" ]; then
  exec "$TL" -c .textlintrc manuscript/
fi
echo "SKIP: textlint 未導入 (npm install --prefix ${TEXTLINT_TOOLDIR:-$HOME/.hermes/tools/textlint} textlint textlint-rule-preset-ja-technical-writing textlint-rule-prh @textlint-ja/textlint-rule-preset-ai-writing textlint-filter-rule-comments)"
exit 0
```

## prh.yml

```yaml
version: 1
rules:
  - expected: Quarto
    patterns:
      - クオルト
  - expected: エージェント
    patterns:
      - エージェーント
```

## .gitignore

```
_site/
.quarto/
*.log
```

## README.md

```markdown
# <name>

longform-writing-pipeline 準拠の執筆リポジトリ。

## ワークフロー

1. spec/outline.md を作り人間承認(approved: true) — longform-outline
2. セクション起草(1カード=1節) — longform-section-draft
3. レビュー反映は patch のみ — longform-revise
4. 統合検査+通読 — longform-integrate

## ゲート

just lint / just check-refs / just coverage / just build-html(just 未導入なら各コマンドを直接実行)
```
