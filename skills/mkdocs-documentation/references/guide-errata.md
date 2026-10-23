# 指南書 A1.1 の誤りと補い

「モジュラーモノリス FastAPI プロジェクトのための MkDocs ドキュメンテーション指南書」（A1.1）どおりに組むと
動かない・足りない点。task_ambi で 2026-10-07 に実測した。雛形（assets/）はすべて反映済み。

## 誤り（そのままでは止まる）

| # | 指南書の記述 | 実際 | 雛形での対処 |
|---|---|---|---|
| E1 | include-markdown に `base_path: docs` | include-markdown にその設定は無い（snippets の設定）。`--strict` だと設定警告で即中断 | 設定を外す。パスは「取り込む側のファイル」からの相対で解決される。gen-files の仮想ページは一時フォルダに置かれるので、図は絶対パスで取り込む |
| E2 | `ENABLE_PDF_EXPORT=1 mkdocs build` | `!ENV` は値を YAML として読むので `1` は整数。exporter の `enabled` は真偽値しか受けず設定エラー | `ENABLE_PDF_EXPORT=true` を渡す（mermaid-to-svg の `enabled_if_env` は空でなければ有効なので両立する） |

## 足りない点（動くが崩れる）

| # | 症状 | 原因 | 雛形での対処 |
|---|---|---|---|
| G1 | README のリンクが全部ずれる | snippets は取り込み先（docs/index.md）基準でリンクを解決しない | README は include-markdown で取り込む（`rewrite-relative-urls` が既定で効く） |
| G2 | hook で app を import すると mkdocs のログが乱れる・重い | アプリの組み立てがルートロガを差し替える／重い依存を読み込む | ダンプは別プロセス（`sys.executable scripts/dump_openapi.py`）。指南書の「serve 中はコード変更が反映されない」も解消する |
| G3 | `mkdocs serve` が再ビルドを繰り返す | ダンプ先（docs/ 配下）を毎回書くと監視が更新と見なす | 内容が変わったときだけ書く |
| G4 | `mkdocs serve` が起動しない | 既定の 8000 番をアプリが使っている | `dev_addr: 127.0.0.1:8001`、`site_url` も同じ所在に |
| G5 | `site/api/SUMMARY/` などのページができ、PDF に混ざる | literate-nav はナビ定義を「ナビに出さない」扱いにするだけでビルドする | `hooks/exclude_nav_files.py` がビルド対象から外す（優先度 -200） |
| G6 | 一括 PDF にしおりが無い（確認項目 1 を満たさない） | exporter の aggregator はページの PDF をつなぐだけ | `hooks/pdf_outline.py` が各ページの PDF のページ数を足し上げ、ナビどおりのしおりを付ける |
| G7 | PDF の漢字が中国語の字形 | フォント未指定だと Chromium が WenQuanYi Zen Hei を選ぶ | `docs/css/pdf.css`（exporter の `stylesheets`）で日本語フォントを指定 |
| G8 | PDF 内で「実行」を検索しても見つからない | 指南書の Noto Sans CJK（CFF）を Chromium が Type3 で埋め込み、「行」「入」「面」「一」などが康熙部首（U+2F00〜）として記録される | TrueType の IPA ゴシック（`fonts-ipafont-gothic`）を優先。`scripts/font_probe.py` で比べられる |
| G9 | 大きなモジュールで PDF 化が `Layout repeated` の ERROR（strict で中断） | `show_source: true` の長いソース表を Paged.js がページに分割できない | `pdf.css` で `details.mkdocstrings-source` を PDF だけ非表示（HTML では残る） |
| G10 | 表の `<PROFILE>` が消える・`[A-Z][A-Z0-9_]*` で autorefs 警告 | table-reader がエスケープするのはパイプ（縦棒）だけ | `hooks/escape_placeholders.py`（content-hazards.md を参照） |
| G11 | Material が「MkDocs 2.0 で全プラグインが壊れる」と警告を出す | MkDocs 2.0 は非互換 | `mkdocs>=1.6.1,<2` で上限を切る。表示だけなら `DISABLE_MKDOCS_2_WARNING=true` で消える |
| G12 | neoteroi の CSS が見当たらない | パッケージに同梱されていない | 入れた版のリリース配布物 `css-v{版}.css` を `docs/css/mkdocsoad.css` に置く |
| G13 | モジュールが 15〜20 を超えると手書きの API ページが破綻 | 指南書も gen-files を発展オプションとしている | gen-files ＋ literate-nav で 1 モジュール 1 ページを生成（`scripts/gen_doc_pages.py`）。設定は mkdocs.yml の mkdocstrings `paths` と `extra.docs_build` から読む |
| G14 | プラグインの並び順が本文とフル版で食い違う | 本文は「mkdocstrings → mermaid-to-svg」、フル版は逆 | mermaid-to-svg は include-markdown（図の本文を差し込む）より後なら動く。雛形は本文の順 |
| G15 | 外部リンク切れで `--strict` が止まる | README・設計文書はコード・非公開メモへリンクする | `validation.links.not_found: info`（文書は書き換えない） |

## 参考値（task_ambi）

- 依存の追加は docs グループの 39 パッケージだけで、既存パッケージの版は不変。gen-files・literate-nav が
  `properdocs`（同じ作者の MkDocs 1.x 継続版）を連れてくるが、ビルドに使うのは mkdocs 1.6.1 本体。
- HTML ビルド約 30 秒。PDF 込みで約 4 分半、1,154 ページ・74.5MB・しおり 264 件。
