---
name: ${PROJECT_NAME}_harness_distribution
description: "Use when Hermesハーネスを機器間移行または公開配布するとき。"
version: 1.0.0
author: ${USER_NAME_LOWER}, Hermes Agent
license: private
metadata:
  hermes:
    tags: [hermes, migration, distribution, task_ambi, harness]
---

# Hermesハーネス移行・配布

task_ambi 4層カンバン組織のハーネス（default プロファイル直下の skills・SOUL・config・agent-hooks・criteria、25役プロファイル）を他機器へ移す、または公開用にサニタイズして配布する作業の規程。移行先でのエクスポート/インポート、公開リポジトリ生成、置換テーブル運用、25役の再現手順を扱う。

## When to Use

- Hermes のプロファイル群・スキル・SOUL・config・hooks・criteria を別機器へ移す・別機器で再現する
- 公開用にパス・機密を除去した配布リポジトリを作る・更新する・push する
- 移行・配布で「何を移すか」「どの公式機構を使うか」「どこに機密が散在するか」を判断するとき
- 使わない: プロファイル単体の作成・役割の移植（${PROJECT_NAME}_persona_migration）、組織の起動（${PROJECT_NAME}_boot）、kanban 運用そのもの（${PROJECT_NAME}_kanban-agent-org）

## 常時ルール
- ~/.hermes を丸ごと rsync しない — 実体の大半は state.db・sessions・cache・logs で、盤面と環境固有パスが混入する。1回限りの機器移動は `hermes profile export/import`、継続配布・公開は distribution 方式を使い分ける。
- 公開版の機密排除の本丸は作者側 .gitignore と置換スクリプト — installer のハード除外は受領者側の保護でしかなく、git add を止めない。
- 秘密は文字列粒度で散在する（skills・各役 memories・criteria・SOUL・cron jobs.json・config.yaml の hooks command と platform_toolsets）。.gitignore では防げないので、置換テーブルは1ファイルに集約し、正方向（公開生成）と逆方向（導入展開）の両方から読む。
- プロファイル配下の config.yaml は配布しない — コメント付きフルテンプレートで、コメントを除けば default とほぼ同一・差分は数行。25役は `hermes profile create --clone-from default` で生成して external_dirs を継承させ、souls/ から SOUL だけ差し替える。
- distribution 機構は1リポジトリ＝1プロファイル — 多役組織の再現は公式機構の範囲外。配布物に SOUL 差分と profiles.txt を置き、導入スクリプトで clone する。
- cron は配布しても自動スケジュールされない — README に導入後の手動有効化手順を明記する。
- config.yaml の編集は hermes config set 経由のみ（hermes-agent skill の不変則を継承）。

## 手順
1. 棚卸し: 秘密の散在を実測する。grep パターン: <vault-name>・192.168.・${USER_HOME}・${KANBAN_RUNS_DIR}。対象: ~/.hermes/skills、各プロファイルの memories・SOUL・config.yaml、~/${KANBAN_RUNS_DIR} の criteria 群、cron jobs.json。
2. 方式選択: 機構の詳細は references/hermes-profile-distributions.md を読む。
3. 配布リポジトリ: distribution.yaml（name 必須・env_requires で必要変数を宣言）+ .gitignore（公式ハード除外リスト準拠）。
4. 公開生成: 置換テーブルの正方向適用 + 機密0件検査をスクリプトに内蔵し、検査不通では push できない形にする。置換テーブル自体は公開リポジトリに入れない（消したい語の一覧そのものになるため）。
5. 導入: .env 実値で逆方向置換 → ~/.hermes 反映 → 25役 clone-from-default 生成 → SOUL 差し替え → agent-hooks 配置 → cron 手動有効化。
6. 検証: HERMES_HOME を別値にしたクリーン環境で profile list・skills list（frontmatter 破損の確認）・hooks 発火・criteria 参照解決・`hermes profile update` でユーザーデータが保持されることを確認する。
7. 運用: 正本更新 → 生成 → push → 導入先 update。配布物は生成物に一本化し手編集させない。

## task_ambi ハーネスの現状
- 移行計画の正本: ${REPO_ROOT}/docs/harness_migration_plan.md（確定版・着手待ち）— 関連作業の前に読む。フェーズ P0〜P7・置換テーブル草案・検証条件はここが正。
- 裁定済み: 公開リポジトリは ${REPO_NAME}_public（GitHub リポジトリ本体はユーザーが作成する）・h01 系 criteria も公開可（機密プロジェクトではない）・cron はそのまま配布。
- task_ambi_public は v2 専用リポジトリ — v3 用に流用しない。
- 公開生成スクリプトは publish_tools/ 配下に置き、生成物リポジトリとは分離する（置換テーブルを含むため）。

## references
- references/hermes-profile-distributions.md — export/import・distribution.yaml・install/update の動作とハード除外リスト
