# SDD 役割とプロファイルの対応表(正本)

sdd-project-lead / sdd-pipeline / sdd-worker-rules の3スキルが参照する共通の対応表。2026-10-07 に人間が確認したもの。

## 対応表

|階層|役割|プロファイル|使うスキル|
|---|---|---|---|
|上位|プロジェクト統括|planner|sdd-project-lead|
|中位|SE|system_engineer|sdd-pipeline|
|下位|architect|architect|sdd-worker-rules(+ 工程の speckit-* スキル)|
|下位|reviewer|code_reviewer|sdd-worker-rules(+ 工程の speckit-* スキル)|
|下位|programmer|programmer|sdd-worker-rules, speckit-implement|
|下位|debugger|debugger|sdd-worker-rules|
|下位|test-engineer|test_engineer|sdd-worker-rules|

使わないプロファイル: project_lead / public_relation / content_writer / structure_designer / analyst / presenter / communication / devops / specification_writer。

## ループ上限

|ループ|上限|
|---|---|
|checklist 修正|1回|
|analyze 修正|3回|
|テスト修正|3回|
|converge|3回|
|統括の手直し|1回|

上限到達時は1段上に判断依頼(作業役→SE→統括→人間)。

## 工程カードの skills 指定(SE が起票時に使う)

|工程|assignee|skills|
|---|---|---|
|01 specify|architect|sdd-worker-rules, speckit-specify|
|02 clarify|code_reviewer|sdd-worker-rules, speckit-clarify|
|03 plan|architect|sdd-worker-rules, speckit-plan|
|04 checklist|code_reviewer|sdd-worker-rules, speckit-checklist|
|05 tasks|architect|sdd-worker-rules, speckit-tasks|
|06 analyze|code_reviewer|sdd-worker-rules, speckit-analyze|
|07 implement|programmer|sdd-worker-rules, speckit-implement|
|08 テスト|test_engineer|sdd-worker-rules|
|09 converge|code_reviewer|sdd-worker-rules, speckit-converge|
|10 最終レポート|code_reviewer|sdd-worker-rules|
|修正(analyze/checklist)|architect|sdd-worker-rules|
|修正(テスト)|debugger|sdd-worker-rules|
|判定 *|system_engineer|sdd-pipeline|
|手直し|system_engineer|sdd-pipeline|
|判断依頼(SE 宛)|system_engineer|sdd-pipeline|
|判断依頼(統括宛)|planner|sdd-project-lead|
