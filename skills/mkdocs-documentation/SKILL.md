---
name: mkdocs-documentation
description: FastAPI のモジュラーモノリス（Python・uv・src レイアウト）を MkDocs（Material）でドキュメント化する。README・設計文書（docs 配下の md・csv・mermaid）・docstring（mkdocstrings の API リファレンス）・FastAPI の REST API（OpenAPI を neoteroi で描画）の 5 種を 1 つのサイトにまとめ、mkdocs-exporter で 1 枚の PDF に一括出力できる状態にする。その前段として、docstring の Args/Returns/項目説明と OpenAPI の summary・引数・項目の説明の欠落を棚卸しして埋める。同梱の雛形と検査スクリプトが、指南書どおりでは止まる・崩れる点（PDF のしおり無し、日本語の部首化け、`<key>` の消失、行頭 # の見出し化など）を潰してある。「MkDocs でドキュメント化して」「ドキュメントサイトを作って」「docstring を整備して API リファレンスを」「REST API ドキュメントが生成されない箇所を直して」「設計書と README をまとめて PDF に」「mkdocs.yml を作って」「mkdocstrings／neoteroi／mkdocs-exporter」など、Python プロジェクトの文書をサイトや PDF にしたい話、docstring・OpenAPI の記述を整えたい話が出たら、MkDocs という語が無くても必ずこのスキルを使うこと。設計文書の中身をコードの実態に合わせて書き直す作業（sync-design-docs）や、Sphinx での構築には使わない。
argument-hint: "[アプリの指定 module:attr（例 api:create_app）] [段 A／段 B]"
compatibility: uv・FastAPI（Pydantic v2）・Node.js の mermaid-cli（mmdc）・Playwright の Chromium・日本語の TrueType フォント（fonts-ipafont-gothic）。MkDocs 1.6 系・Material 9.7 系・mkdocs-exporter 6.2 で確認。scripts はプロジェクトの venv で動かす（pyyaml・pypdf・playwright は docs 依存に含まれる）
---

# FastAPI モジュラーモノリスを MkDocs でドキュメント化する

5 種の文書（README・設計文書の md/csv/mermaid・docstring・REST API）を 1 つの MkDocs サイトにまとめ、
1 枚の PDF にも出せる状態にする。作業は 2 段に分かれ、どちらか一方だけでも使える。

- **段 A（記載）**: docstring と OpenAPI の説明の欠落を棚卸しして埋める。サイトに載せる前に中身をそろえる。
- **段 B（構築）**: サイトと一括 PDF を組み、機械検査で 5 種がそろっていることを確かめる。

元にした「MkDocs ドキュメンテーション指南書 A1.1」は、そのままでは止まる箇所が 2 つ、崩れる箇所が十数ある。
雛形（`assets/`）はすべて直してあり、理由は `references/guide-errata.md` にある。指南書を渡されても、
雛形の形を優先し、違いは完了報告で伝える。

以下、`S=~/.claude/skills/mkdocs-documentation/scripts` とする。スクリプトは**対象リポジトリのルートで、
そのプロジェクトの venv で**動かす（アプリを import するため）。前置きの `$PY` は、docs 依存を入れる前は
`uv run --with pyyaml python`、入れた後は `uv run --group docs python` にする（pyyaml・pypdf・playwright を使う）。

## 既定の方針

次は既定として扱い、毎回は聞かない。プロジェクトの規約や状況が合わないときだけ AskUserQuestion で確かめる
（推奨案を先頭に置く）。

| # | 論点 | 既定 | 理由 |
|---|---|---|---|
| 1 | Pydantic の項目説明の書き方 | 項目の直後に属性 docstring。HTTP に出る型だけ `model_config` に `use_attribute_docstrings=True` | 1 つの記述が OpenAPI と mkdocstrings の両方に載る。`Field(description=)` は mkdocstrings が描かない。LLM 向けのスキーマに付けると送る中身が変わる |
| 2 | 項目説明の範囲 | 公開クラスの全項目（モジュール間の受け渡し型も） | 指南書の「クラス: 役割と Attributes」 |
| 3 | 画面（フロントエンド）のコード | API リファレンスから外す（`--exclude-module ui` など） | 指南書の対象外。画面の内部関数で PDF が膨らむ |
| 4 | サイト外へのリンク（コード・非公開メモ） | `validation.links.not_found: info`。README・設計文書は書き換えない | README は GitHub、設計文書は Obsidian でも読む正本 |
| 5 | 正本の OpenAPI があるとき | summary・成功応答の説明は正本から転記。**応答コードは足さない** | 正本との二重管理を最小にする。契約テストが宣言済みの応答コードを数えていることがある |
| 6 | 正本と実装の食い違い・判断の要る残り | 埋めずに報告し、tracker があれば起票 | 推測で補完すると、どちらが正か分からなくなる |
| 7 | コミット | しない（報告で候補を示す） | 同じ作業ツリーを他の作業が使っていることがある |

## 段 0 準備

1. プロジェクトの規約（CLAUDE.md・憲章など）を読み、次を確かめる。
   - アプリの指定（`module:attr`。アプリ工場か FastAPI インスタンス）。組み立てに `.env` などが要るか。
   - mkdocstrings の対象にする `src`（凍結物・試作・画面を外す）。設計文書の置き場（docs 配下）。
   - 正本の OpenAPI（あれば）と、それを読む契約テスト。lint の行幅（ruff は全角を幅 2 で数える）。
   - 追記専用の文書（設計判断記録など）。描画のためでも書き換えない。
2. **同じ作業ツリーを使う他の作業**（別セッション・AI の自動実行・同じ `.venv` で動くアプリ）を確かめ、
   書く前に知らせる。読むだけの git は `git --no-optional-locks` で index のロックを取らない。
3. tracker があれば作業を起票する（bd なら `bd create` → `bd update --claim`）。

## 段 A docstring と OpenAPI の記載

### A1. 棚卸し

```bash
$PY $S/docstring_audit.py summary --src {src} --src {src} --exclude-module ui
$PY $S/openapi_tools.py audit --app {module:attr}
$PY $S/openapi_tools.py compare --app {module:attr} --spec {正本.yaml}   # 正本があるとき
```

- `docstring_audit` は ruff が見ない欠落（Args/Returns/Raises の節・項目説明・パッケージ docstring）を数える。
  `mkdocs.yml` ができた後は `--src` を省くと、mkdocstrings の `paths` と除外モジュールを読む。
- `openapi_tools audit` は summary の自動生成・引数と項目の説明の欠落・描画を壊す書式（行頭 `#`・`<占位子>`）・
  機械的な型名を数える。数え方と直し方は `references/content-hazards.md`。

### A2. docstring を埋める

モジュール単位で、`docstring_audit.py todo {ファイル…}` → コードを読む → spec を書く → `doctool.py --dry` →
適用 → 整形・lint・そのモジュールのテスト。spec の書き方と規則は `references/docstring-spec.md`。
Raises 節と、docstring そのものが無いものは手で書く。

### A3. OpenAPI を埋める

1. summary・成功応答の説明: 正本があれば `openapi_tools.py transcribe --spec {正本} {router…}`。無ければ手で
   `summary=`・`response_description=` を書く（行頭を `#` にしない、`<key>` は `{key}`）。
2. パス・クエリ引数: router のモジュールに `XxxPath = Annotated[str, Path(description="…")]` を置いて使う。
3. エラー応答: 既に宣言している 404・409・422 の `responses` に `description` を足す（コードは足さない）。
4. アプリ全体: `FastAPI(description=…)`。タグの説明（`openapi_tags`）は、組み立ての規約（モジュール追加で
   アプリ定義を触らない、など）に反するなら入れずに報告する。
5. HTTP の型: 属性 docstring を書き（A2 の spec の ATTRS）、`openapi_tools.py add-flag --app {module:attr}`。
   型別名の enum は `Annotated[Literal[…], Field(description=…)]`。
6. 各バッチの後に、lint・型検査と、OpenAPI を読む契約テストを流す。

### A4. 再確認

```bash
$PY $S/openapi_tools.py audit --app {module:attr}
$PY $S/openapi_tools.py compare --app {module:attr} --spec {正本.yaml}
$PY $S/openapi_tools.py components-map --app {module:attr}      # 型と定義クラスの対応
uv run --with pyyaml --with openapi-spec-validator python $S/openapi_tools.py validate --app {module:attr}   # 仕様として妥当か
```

残る差（正本に無い応答、応答ヘッダの未宣言、機械的な型名など）は、判断が要るものとして報告・起票する。
最終的な描画の確かめは段 B の `verify_site.py` で行う（REST API の h1 の数・summary の表示）。

## 段 B サイトと一括 PDF

### B1. 雛形を置く

```bash
$PY $S/scaffold.py --app {module:attr} --src {src} … --exclude-module ui \
    [--design-dir design] [--exclude-docs /private/ …] [--readme-section]
```

置くもの: `mkdocs.yml`・`hooks/`（OpenAPI のダンプ・占位子のエスケープ・ナビ定義の除外・しおり）・
`scripts/`（ダンプ・ページ生成）・`docs/index.md`（README の取り込み）・`docs/openapi/index.md`・
`docs/css/pdf.css`・`puppeteer-config.json`、`.gitignore` の追記。既存ファイルは上書きしない。
設定は `mkdocs.yml` の `extra.docs_build` に集まっている（アプリの指定・設計フォルダ・除外モジュール・PDF の出力先）。

### B2. 依存と配布物

scaffold が最後に表示するコマンドを順に打つ。

```bash
uv add --no-sync --group docs "mkdocs>=1.6.1,<2" …   # 一覧は scaffold の表示
python3 $S/lock_diff.py                  # 既存パッケージの版が 1 つも動いていないこと（追加だけのはず）
uv sync --group docs --inexact          # 稼働中のアプリの venv から余分なものを消さない
curl -sSfL -o docs/css/mkdocsoad.css "https://github.com/Neoteroi/mkdocs-plugins/releases/download/v$V/css-v$V.css"
uv run --group docs playwright install chromium
```

PDF には `mmdc`（`npm install -g @mermaid-js/mermaid-cli`）と日本語の TrueType フォント（`fonts-ipafont-gothic`）も要る。
入っていなければユーザに頼む（sudo が要る）。フォントで迷ったら `font_probe.py` で比べる。

### B3. HTML を通す

```bash
DISABLE_MKDOCS_2_WARNING=true uv run --group docs mkdocs build --strict
```

警告が出たら原因を直して 0 にする。典型は `references/guide-errata.md` と `references/content-hazards.md` にある
（autorefs の「相互参照先が無い」＝本文の `[…][…]`、mkdocstrings の解決失敗＝ `paths` の誤りなど）。

### B4. 検証

1. **HTML**: `$PY $S/verify_site.py` と `$PY $S/check_mermaid.py`。
   設計文書の md・図・表がページになり、表の形が CSV と一致し、占位子が表示され、API リファレンスに描画があり、
   REST API の summary が全部表示され h1 が 2 個で、ホームに README があることを見る。
2. **PDF**（数分かかるのでバックグラウンドで）:
   `ENABLE_PDF_EXPORT=true DISABLE_MKDOCS_2_WARNING=true uv run --group docs mkdocs build --strict`
   → `$PY $S/check_pdf.py --expect {README の題} --expect {設計文書の一文} --expect {CSV のセル}
   --expect {図中の語} --expect {docstring の一文} --expect {REST API の summary}`。しおり・部首化け 0・5 種の文字列を見る。
3. **serve**: `mkdocs serve` を起動し、`http://127.0.0.1:{port}/` が 200、REST API が描かれ、ビルドが 1 回で
   止まる（再ビルドが繰り返されない）ことを見る。
4. **既存のゲート**: lint・型検査・テスト全体（uv.lock が変わったので）。

PDF 込みのビルドは図を SVG 画像に置き換えて site/ を作り直す。`check_mermaid.py` は HTML だけのビルドの後に流し、
PDF 込みのビルドを最後にすると、site/ に PDF が残る。

## 完了報告

この順で書く。

1. 結論（何ができる状態になったか・何が残ったか）を 1〜2 文。
2. 使い方（serve と PDF のコマンド。ポート）。
3. 確認したこと（数で）: 設計文書の md／図／表のページ数・API リファレンスのモジュール数・REST API の操作数・
   PDF のページ数としおり数・ゲートの結果。
4. 指南書から変えた点（誤り・補い）。
5. 判断が要る残り（起票した ID）。
6. 変更したファイルと、コミットしていないこと（同じ作業ツリーを使う他の作業があれば、その状況）。

## 参考 task_ambi での実測（2026-10-07）

- 段 A: Args 312・Returns 259・項目説明 729 の欠落を埋め、OpenAPI は summary 53・引数 37・項目 209 の説明を付けた。
  再確認で、行頭 `#N` の docstring 76 箇所（h1 化）・項目説明の `<…>` 7 件・型別名の説明なしを見つけて直した。
- 段 B: 設計文書 md 47・図 41・表 16、API リファレンス 117 モジュール、REST API 53 操作。HTML・PDF とも `--strict` で通り、
  PDF は 1,154 ページ・しおり 264 件・74.5MB（約 4 分半）。占位子の消失は CSV 133・md 12・summary 4 を hook で表示させた。
