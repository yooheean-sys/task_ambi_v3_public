---
name: spec-completeness-audit
description: "Use when auditing a speckit specs tree for unresolved items."
version: 1.0.0
author: Hermes Agent + ${USER_NAME_LOWER}
license: MIT
metadata:
  hermes:
    tags: [speckit, spec, audit, serena, task-ambi]
    related_skills: [taskambi_persona_migration]
---

# 仕様完全性オーディット（speckit 型 specs/ ツリー）

## When to Use

- `specs/` 配下に feature ごとの spec.md / plan.md / tasks.md / design-sync.md / checklists/ がある
  リポジトリで、「仕様の不完全なところ・未決事項を探して」のように監査を求められたとき。
- 既知の実例: `~/project/task_ambi/task_ambi_2609`（17 フィーチャー。未決は design-sync の
  B 表＝ユーザ裁定待ち行列に集約される運用）。

## 手順

1. **Serena を使うときの起動順**（MCP サーバ serena が接続済みの前提）:
   `tool_search` で serena ツール群を読み込む → `mcp__serena__initial_instructions` を呼ぶ
   （応答の `<session>` にセッションIDが載る）→ `activate_project(プロジェクトの絶対パス, session_id)`。
   以降 `find_symbol` / `get_symbols_overview` / `find_referencing_symbols` が使える。
   Serena の行番号は **0-based**。
2. **規模の把握**: `for d in specs/*/; do wc -l < $d/spec.md ...` でフィーチャー一覧と行数を出す。
   監査対象の全体像はここで掴む（spec.md の行数差が激しい feature は深掘り候補）。
3. **未決マーカーの全体走査**:
   ```bash
   rg -n "TODO|FIXME|TBD|要確認|未確定|未決|要議論|裁定待ち|未裁定" -g "*.md" specs/
   ```
   落とし穴: `???` のようなパターンを grep -E に混ぜるとうまく解釈されず、
   総カウントが意味のない巨大値になる。マーカー語は固定語だけにする（-F か パターン分割）。
4. **B 表（ユーザ裁定待ち行列）の抽出** — 主成果物。`design-sync.md` の行頭 `| **B-nn**` を
   正規表現で抽出し、**行自身の状態列**（裁定済み / 解決済み / ユーザ裁定待ち / 未裁定 /
   記録のみ）で開閉を判定する:
   - 同じ B-nn が本表と起票ログ（実装セッションの記録節）の**両方に現れる**ことがある。
     「未裁定」という語は「〜は解消していない」という解決済み報告の文中にも出るので、
     行の冒頭3000字で雑に判定すると解決済み行を誤検知する。行末（状態列・根拠列）を優先する。
   - design-sync の冒頭や末尾に「未裁定の待ち行列: B-xx〜 の N 件」のような**自己宣言**があれば、
     それが正本。機械抽出と食い違ったら自己宣言を優先し、食い違い自体を報告に載せる。
   - 「裁定待ちのまま残るもの（再掲）」のような節は、表から漏れた未決の完璧な一覧なので必ず読む。
5. **未消化タスク**: `rg -n "^- \\ [ ]" */tasks.md`（または grep -c）。ただし
   「未完了」≠「不完全」: ユーザ指示（例: git 操作の禁止）で意図的に止まっているタスクは
   **待ち**と分類し、技術的に未了の再判定タスクだけを「未了」と区別して報告する。
6. **チェックリストの未チェック数**: 数えるが、すぐ「未実施」と結論しない。
   `checklists/verification.md`・`traceability.md` は**レビュー担当者所有**で AI が書き換えない
   レジームのことがある（design-sync に所有者の明記がある）。所有者を確認してから
   「プロセス面の未完了」として報告する。
7. **現物照合（Serena）**: 報告に載せる未決論点から 1〜2 件をサンプル検証する。
   `find_symbol(name_path_pattern=..., relative_path=..., include_body=True)` でメソッド本体を取り、
   spec/設計判断の主張（例: 「古い辺を削除しない」）がコードと一致するか確かめる。
   解決済みと記録された項は、例外クラス等の docstring に決着が書かれていることで確認できる
   （docstring が決着記録の定置になっている運用が多い）。
   落とし穴: find_symbol の include_kinds に LSP kind を渡すと空配列で返ることがある。
   まず kind を絞らず名前だけで探す。
8. **報告の構成**（この順。表で feature 別に）:
   (a) 憲章レベルの未決（diff 案が書いてあるのに適用待ちの項は明示） →
   (b) feature 別未決（B 表行の ID + 一行要約） →
   (c) 未消化タスク（待ちと未了を区別） →
   (d) チェックリスト未チェック（所有者を明記） →
   (e) 現物照合の結果（裏付け取れた論点と解決済みを確認できた論点の両方）。
   最後に優先度順のまとめを付ける。「契約の正本が埋めを要求したまま」「台帳・plan・憲章への
   追随漏れ」「実行不能な仕様（移植元・供給元が存在しない）」「プロセス未完了」の4類型に分けると
   読み手が着手判断をしやすい。

## やらないこと

- 設計判断記録（`p5_decision_log.csv`・`設計判断_V4-D**` 等）は append-only・ユーザ採番なので
  監査で書き換えない。未決は報告するだけで、裁定はユーザに委ねる（B 表のレジームどおり）。
- spec 全文を読み切ろうとしない。マーカー走査と B 表抽出で位置を特定し、必要な節だけ読む。
