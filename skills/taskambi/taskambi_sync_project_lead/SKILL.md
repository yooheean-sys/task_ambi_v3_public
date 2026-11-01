---
name: taskambi_sync_project_lead
description: project_lead_* 全複製の SOUL.md 共通節を点検・同期する。
version: 0.1.0
author: ${USER_NAME}, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [kanban, project_lead, SOUL, maintenance, harness]
    related_skills: [taskambi_kanban-agent-org]
---

# taskambi_sync_project_lead Skill

project_lead_* プロファイル（全複製）の SOUL.md を「共通指示は全複製で同一・プロジェクト固有部は各プロジェクトのまま」に保つ点検・同期ツール。共通節の正本（唯一の真実の源）はスキル同梱の `references/project_lead_canonical.md`。スクリプトは Python 標準ライブラリのみで動く。

## When to Use

- project_lead の SOUL.md 運用ルールを改訂し、全複製へ同じ改訂を適用するとき（taskambi_kanban-agent-org の「発散管理: 改訂は全 project_lead_* 複製へ適用」規則の実行）
- project_lead_* 間で共通指示が発散していないか点検するとき
- 新規 project_lead_<名前> を複製した後、正本と一致しているか確認するとき
- Don't use for: プロジェクト固有節（ルートパス・ディレクトリ契約など）の内容設計。それは人間の裁定＋ capture で行う

## 構造契約（スクリプトが前提とする SOUL.md の形）

- SOUL.md = **固有ヘッド** + **共通節**
- 共通節 = `## あなたは誰か` の見出し行から EOF まで（あなたは誰か／目標／守ること／判断点の裁定／レビュアーとして呼ばれたとき／この役割だけの守り）。**全複製で同一であるべき部分**
- 固有ヘッド = 冒頭〜その直前（タイトル／担当プロジェクト／プロジェクトルートとディレクトリ参照）。原則プロジェクト固有だが、正本の LINE / BLOCK 仕様に該当する「共通指示行」だけは同期対象
- 新しい共通条項は `## あなたは誰か` 以降に追加する。固有ヘッド側に共通節の見出しを置かない

## How to Run

`skill_view('taskambi_sync_project_lead')` で skill_dir を取得し SCRIPT を組み立てて `terminal` で実行する。

## Quick Reference

```bash
SCRIPT="<skill_dir>/scripts/sync_project_lead_soul.py"
python3 "$SCRIPT" check              # 点検（読み取り専用・いつでも可）
python3 "$SCRIPT" sync               # 修正内容のプレビュー（dry-run・書き込まない）
python3 "$SCRIPT" sync --apply       # 適用（backups/ へ自動バックアップ）
python3 "$SCRIPT" capture --from project_lead_xxx_others_pj   # 正本の再採録
# 絞り込み: --only g01 （ディレクトリ名の部分一致）
```

終了コード: 0=全クリーン / 1=発散あり / 2=構造エラー。`check` と dry-run は安全。**`sync --apply` は人間承認があってからのみ実行**（harness 規約: SOUL 改訂の適用は本文に人間承認の明示があるときだけ）。承認を求めるときは clarify で選択肢＋推奨を提示する。

## Procedure（改訂ループ）

1. いずれか1枚の SOUL.md を人間承認の上で改訂する（patch ツール等）
2. `capture --from <改訂したprofile>` で正本を再採録する（共通節 tail と既存 LINE/BLOCK の文言が更新される。required/except の指定は保持される）
3. `sync`（dry-run）で差分を確認し、人間承認を得て `sync --apply`
4. `check` で終了コード 0 を確認。適用されたファイルは `<profile>/backups/SOUL.md.pre-sync-<時刻>.md` にバックアップ済み
5. SOUL の変更は**次回 spawn から反映**（実行中の run には効かない）。報告にその旨を含める

完了基準: `check` が終了コード 0（全複製の共通節＝正本）で、固有ヘッドの非同期部分が1行も変わっていないこと。

## 正本ファイルの書式（references/project_lead_canonical.md）

- `TAIL>> … <<TAIL`: 共通節本体（`## あなたは誰か` 行から EOF 相当）。全ファイルへそのまま適用
- `LINE <名前> required=yes|no except=<profile名,…>` + `ANCHOR>>` + `TEXT>>`: 固有ヘッド内の共通指示行。ANCHOR は行頭前方一致。required=yes の行が無い場合は**報告のみ（自動挿入しない）**
- `BLOCK <名前> …` + `BLOCK_ANCHOR>>` + `BLOCK_TEXT>> … <<BLOCK_TEXT`: 複数行ブロック（例: 標準ディレクトリ統一定義）。アンカー行＋空白で字下げされた後続行を1ブロックとして同期
- `except=` は意図的なプロジェクト差分を持つプロファイルの除外（現行: workspace起票行は p01＝ノート/コード2拠点、xxx＝フォールバック専用の言い回し）
- 共通化したい行が増えたら人間の文言裁定の上で LINE/BLOCK を追加する。「旧文言が単に古い」行だけを入れること。プロジェクト固有の理由で文言が違う行は入れない

## Pitfalls

- **プロファイルディレクトリ名は小文字化される**（例: project_lead_${PROJECT_P01_NAME}）。`--only` / `except=` はディレクトリ名で指定する（assignee 名の ${PROJECT_P01_NAME} ではない）
- `## あなたは誰か` が 0 個または 2 個以上あるファイルは**構造エラーとして一切書き換えない**。人間に報告する
- 複製は実体コピーなので、片方だけ直した修正は他に伝わらない。必ず capture → sync の経路で全複製へ反映する
- 共通節を1枚だけ手で直して capture せずに sync すると、その修正は正本で上書きされて消える。改訂は必ず「1枚改訂 → capture → sync」の順で行う
- check で発散を検出したら、適用前に新旧判定をする（正本と複製の mtime、関連ファイルの実在、組織スキルの記録など）。複製側が新しい改訂なら `sync --apply` ではなく `capture --from <複製>` で正本を再採録する。旧正本のまま sync --apply すると複製側の改訂が消える（2026-10-16 実例: 役別表2段構成への改訂が capture 前で放置され、正本だけ旧文言だった）
- capture は正本を自動バックアップする（`references/project_lead_canonical.md.pre-capture-<時刻>.bak`）。採録元にアンカー行が無い LINE/BLOCK は旧文言が保持され警告表示になる。BLOCK 等の改訂を含む採録では、その BLOCK を**持つ**プロファイルを capture 元に選ぶ（required=no の BLOCK 行なしプロファイルから採録すると BLOCK の改訂が正本へ反映されない）
- スクリプトは SOUL.md 以外（config.yaml / .env / memories 等）には一切触れない。.env・鍵は読み取りも禁止（harness 規約）

## Verification

- `python3 "$SCRIPT" check` → 終了コード 0・全プロファイル「発散なし」
- 適用直後は `<profile>/backups/SOUL.md.pre-sync-*.md` との diff が「意図した共通行の置き換えだけ」であることを確認する
- `hermes profile list` で対象プロファイルが削除・改名されていないか確認する
