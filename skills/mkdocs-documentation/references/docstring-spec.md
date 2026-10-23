# docstring の記載（doctool の spec の書き方）

`scripts/doctool.py` は、spec（Python ファイル）に書いた説明を docstring へ機械的に差し込む。
1 関数ずつ手で編集するより速く、字下げ・節の順・行幅（全角は幅 2）を間違えない。
既にある節は触らない（足すのは**無い節だけ**）。

## spec の形

```python
# spec_board.py（scratchpad など、リポジトリの外に置く）
from common_texts import CFG_INIT   # 同じフォルダの別 spec・共通文言を import できる

B = "packages/features/board/src/board/"   # リポジトリルートからの相対

FUNCS = {
    B + "service.py": {
        "BoardService.show": {
            "args": {"issue_id": "読む課題の識別子。"},     # 引数は全部（self・cls を除く）。過不足があれば止まる
            "returns": "課題 1 件（依存先の要約を含む）。",
        },
        "BoardService.close": {"args": {...}},               # 戻り値が None なら returns は書かない
        "iter_rows": {"yields": "1 行ずつの辞書。"},           # ジェネレータは yields
    },
}

ATTRS = {
    B + "models.py": {
        "BdResult": {                                       # クラスの修飾名（入れ子は Outer.Inner）
            "rc": "終了コード。",                             # 項目名 → 説明（既に属性 docstring があれば止まる）
            "json": "機械可読出力を読んだ値。読めなければ `None`。",
        },
    },
}
```

適用:

```bash
python ~/.claude/skills/mkdocs-documentation/scripts/doctool.py spec_board.py --dry   # 差分を見る
python ~/.claude/skills/mkdocs-documentation/scripts/doctool.py spec_board.py         # 書く
uv run ruff format {対象}; uv run ruff check {対象}                                    # 整形と D417 などの確認
```

`*args`・`**kwargs` は spec では星なしの名前で書く（Args 節には `**kwargs:` の形で出る）。

## 書き方の規則

- Google style・日本語。1 行目は句点で終わる完結した 1 文（既存の docstring は書き換えない）。
- 書くのは「何を受け取り、何を返すか」。引数は意味・単位・`None` の意味、戻り値は形と「無いとき」を書く。
- Protocol の実装メソッドは、Protocol 側に書いた文言を spec で再利用する（同じ内容を二重に考えない）。
- `<key>` の形は使わず `{key}` にする（描画で消える）。行頭を `#` にしない（見出しになる）。
- 同じ文言（設定の読み口・`__init__(**overrides)`・ハンドルの `router` など）は共通の spec モジュールにまとめる。
- 1 回に 1 モジュールずつ: `docstring_audit.py todo {ファイル…}` → コードを読む → spec → `--dry` → 適用 →
  整形・lint・そのモジュールのテスト。最後に `docstring_audit.py summary` で 0 を確かめる。

## doctool が足さないもの

- Raises 節（例外の条件はコードを読んで書く必要があるので手で足す。棚卸しは数える）。
- モジュール・クラス・関数の docstring そのもの（ruff の D1xx で強制されていることが多い。無ければ手で書く）。
