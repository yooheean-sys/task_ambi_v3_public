# 生成・描画を壊す書き方と、その直し方

コードや文書の**書き方**が原因で、docstring・OpenAPI が生成されない、または描画で崩れる・消える箇所。
棚卸し（`docstring_audit.py`・`openapi_tools.py audit`）と試し描画（`verify_site.py`）で見つかる。

## docstring・説明文

| 書き方 | 起きること | 直し方 |
|---|---|---|
| 1 行目が `#1 プロジェクト一覧。` | Python-Markdown は `#` の直後に空白が無くても見出しにする。REST API ページ（description）と API リファレンスに h1 が並び、目次と PDF のしおりが崩れる | 行頭を `#` にしない（`操作 #1 …`）。`verify_site.py` が REST API の h1 の数で検出する |
| `projects/<key>/agents.yaml`（バッククォートの外） | `<key>` が HTML タグとして扱われ、表示から消える | 自分で書く文は `{key}` 形式にする。正本から転記した文・設計文書は書き換えず、`escape_placeholders.py` に任せる |
| 項目説明に `` `member:<id>` `` | neoteroi の項目表は Markdown を処理しないので、バッククォートの中でも `<id>` が消える | `{id}` 形式にする |
| `<title>`・`<area>`・`<body>` という占位子 | HTML の要素名と同じなので、要素名の一覧で残すと表が途中で壊れる | 設計文書のページは `<br>` 以外をすべてエスケープ（雛形の既定） |
| `[A-Z][A-Z0-9_]*`（正規表現） | 参照リンク `[…][…]` と解釈され、autorefs が「相互参照先が無い」と警告（strict で中断） | 設計文書のページでは角括弧もエスケープ（雛形の既定） |

## Pydantic・FastAPI

| 書き方 | 起きること | 直し方 |
|---|---|---|
| `Field(description=…)` だけ | OpenAPI には載るが、mkdocstrings（griffe-pydantic なし）は項目の説明として描かない | 項目の直後に属性 docstring を書き、HTTP に出る型だけ `model_config` に `use_attribute_docstrings=True`（`openapi_tools.py add-flag`）。1 つの記述が両方に載る |
| LLM の道具の引数・構造化出力の型に `use_attribute_docstrings` | LLM に送るスキーマが変わり、振る舞いが変わる | 付けない（`Field(description)` がある型は触らない） |
| `type RecordStatus = Literal["running", "done"]` | components に説明の無い型が出る（型別名の docstring は載らない） | `type X = Annotated[Literal[…], Field(description="…")]` |
| RootModel の `root` | 項目説明は出ない | 型の説明はクラス docstring で書く |
| summary 未指定 | 関数名から英語の `Create Kickoff` が自動で付く | `summary=` を付ける。正本 OpenAPI があれば `openapi_tools.py transcribe` で転記（正本と二重管理になる点は報告する） |
| パス引数 `project_key: str` | 引数の説明が空 | ルータのモジュールに `ProjectKeyPath = Annotated[str, Path(description="…")]` を置いて使う |
| 応答の説明 | 成功応答は `Successful Response`、自動の 422 は `Validation Error` | `response_description=`、既に宣言している 404・409・422 は `responses` に `description`。**正本に無い応答コードは足さない**（契約テストが宣言を数えていることがある） |
| 同名のクラスが別モジュールに 2 つ | `settings__schemas__DetailBody` のような機械的な型名 | クラス名を変える（判断が要る）。入出力で型が分かれる `-Input`／`-Output` は `FastAPI(separate_input_output_schemas=False)` でまとまる |
| router に `from __future__ import annotations` と局所の `Depends(provider)` | FastAPI が注釈を解決できず、依存注入の引数を**素のクエリ引数**と誤読する | 該当の router では future import を置かない。`openapi_tools.py compare` が「正本に無い query 引数」として検出する |

## 描画ツール（neoteroi）の仕様で直せないもの

応答の説明・型の説明を表示しない（`200 OK` のように状態名だけ）。項目表の中の Markdown を整形しない。
必要なら Swagger UI などを併設する（`mkdocs-swagger-ui-tag`。PDF には不向き）。

## 環境・作業の進め方

- **アプリの組み立ての副作用**: OpenAPI のダンプはアプリ全体を組み立てる。`.env` や外部コマンドが要る、
  不在の設定フォルダに雛形を書く、などがあれば、ダンプはその環境でしか動かない。README に明記し、
  揃わない環境向けに `SKIP_OPENAPI_DUMP=1` を案内する。
- **稼働中のアプリと venv**: アプリが同じ `.venv` で動いているなら、`uv add --no-sync --group docs …` →
  uv.lock の差分で既存パッケージの版が動かないことを確認 → `uv sync --group docs --inexact`（余分なものを消さない）。
- **同じ作業ツリーを使う他の作業**（別セッション・AI の自動実行）: 書き込む前に知らせ合う。読むだけの git 操作は
  `git --no-optional-locks` で index のロックを取らない。
- **設計判断記録などの追記専用文書**は、描画のために書き換えない（浅い字下げの入れ子リストが平らになる、程度は許容して報告）。
