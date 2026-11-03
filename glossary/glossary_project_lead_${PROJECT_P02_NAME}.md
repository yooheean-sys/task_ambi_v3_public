---
version: 0.1
updated: 2026-11-03
status: sample（用語統一機構の動作確認用。項目は実運用に合わせて人間が改訂する）
applies_to: [project_lead_${PROJECT_P02_NAME}]
common_core: glossary_project_lead_xxx_others_pj.md
---

# 用語集 — project_lead_${PROJECT_P02_NAME}

## 0. 適用と読み込み順序

- 本ファイルは project_lead_${PROJECT_P02_NAME} の**プロジェクト固有の用語**を定める。共通用語は `${KANBAN_RUNS_ROOT}/glossary_project_lead_xxx_others_pj.md`（§1 共通用語）が正本である
- 共通用語を先に読み、その上に本ファイルの固有用語を適用する。**競合時は本ファイル（プロジェクト固有）を優先**する（criteria の役別優先と同じ規則）。本表で共通用語を緩める改訂は行わない（必要なら共通側の改訂として人間に提案する）
- 用語集の記載と `.hermes.md`（ディレクトリ契約）の記載が食い違うときは契約を優先し、食い違いを自カードの kanban_comment に記録する
- 用語集の追加・変更は project_lead 自身が行わない。「改訂候補: 用語集 …」で始める1文を kanban_comment に記録し、人間が改訂する（共通用語は共通用語集側、プロジェクト固有は本ファイル側が宛先）

## 1. プロジェクト固有の用語（サンプル）

| 用語 | 統一する意味・表現 | 使わない表記（類似表現） |
|---|---|---|
| 資材ディレクトリ | `resources/`（実在ディレクトリ名。契約文書に `resource/` と書かれている実測ズレは実在名を正とする） | resource/、assets/ |
| 成果物配置先 | `projects/` 配下（プロジェクト契約どおり） | outcomes/（本プロジェクトの成果物先として指定しない） |

## バージョン履歴

- v0.1（2026-11-03）: 用語統一機構の動作確認用サンプルとして初版（ユーザー指示）
