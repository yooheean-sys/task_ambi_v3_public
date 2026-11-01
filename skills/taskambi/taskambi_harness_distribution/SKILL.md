---
name: taskambi_harness_distribution
description: "Use when Hermesハーネスを機器間移行または公開配布するとき。"
version: 1.1.0
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
- 使わない: プロファイル単体の作成・役割の移植（taskambi_persona_migration）、組織の起動（taskambi_boot）、kanban 運用そのもの（taskambi_kanban-agent-org）

## 常時ルール
- スキルの配布対象は正本 `harness/skills.txt` の明示許可リストで管理する。各行は `harness/skills/` 相対のスキルディレクトリ（例 `vault/vault_custom_scripts`・`pbi`）。未登録スキルの自動追加や、リスト欠落時の全件コピーをしない。
- 空リストはスキル0件として扱う。登録先の欠落・不正パス・重複・リンクは書き込み前に失敗させる。依存スキルも個別に登録し、導入先の未登録スキルは勝手に削除しない。
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
6. 検証: `HOME` と `HERMES_HOME` の両方を分離した環境で、公開生成 main → 生成済み installer → 実 Hermes CLI による25役作成まで検証する。例示2スキルだけの生成・配置、未登録の除外、空リスト、異常系、既存スキル保持、機密スキャン、再生成の冪等性を確認する。再現コマンドは正本の `uv run python tests/verify_harness_skill_allowlist.py`。更新経路は `hermes profile update` ではなく `install_local.sh` の再実行。
7. 運用: 正本更新 → 生成 → push → 導入先 update。配布物は生成物に一本化し手編集させない。

## 公開生成スクリプトの落とし穴

- **複合名は完全名エントリで置換する**: `project_lead_${PROJECT_G01_NAME}` のような役割+プロジェクトの複合名は、置換テーブルに完全名キーとして登録する。単体トークン（`g01`・`${ORG_NAME}`）の部分置換だけでは途中まで置換した残骸（`project_lead_g01_${ORG_NAME}` 形）が生成物に残る。テーブルはキーの長い順に適用されるので完全名が先に効く。生成スクリプトの自己テスト期待値も新形に合わせて更新する。
- **大文字小文字の別形は両方エントリする**: profile ディレクトリ名は hermes が小文字化する（`project_lead_${PROJECT_P01_NAME}`）が criteria ファイル名は正式名のまま（`criteria_project_lead_${PROJECT_P01_NAME}.md`）。両形を同じ `${PROJECT_*_NAME}` プレースホルダへ置換する。
- **正本の名は生成テキストに直書きしない**: README 等の生成文書で正本リポジトリ名を参照する箇所は `${REPO_NAME}` で書く。正本名自体が F10 走査語になるため直書きは置換漏れになる。
- **README.md はスクリプトの README_TEXT から生成される**: README の修正は生成物ではなく README_TEXT に対して行う（手順 7「手編集させない」の具体的形）。
- **公開固有ファイルは保存機構へ登録する**: 正本 harness/ に無い生成物側専用ファイル（install_local.sh・.pre-commit-config.yaml・agent-hooks/secret_scan.py 等）は regenerate（全消去→再書き出し）で失われる。PRESERVED_FILES 相当の保存リストに登録し generate 後に復元する。新たに公開側だけに置くファイルを作ったら必ずリストへ追加する。
- **正逆テーブルと読み込み側を三方同時更新**: 正方向テーブルにキーを増やしたら REVERSE_MAP と install_local.sh の PLACEHOLDER_MAP・冒頭キー一覧コメントにも同名キーを追加する。検証は install_local.sh --replace-test に全キーを埋めた合成 .env を渡して行う（空の env は置換スクリプトが空になり sed がエラーで止まる。未使用キーの WARN 行は正常・env_requires 12 変数より置換テーブルのキーが多い設計）。

## task_ambi ハーネスの現状
- 移行計画の正本: ${REPO_ROOT}/docs/harness_migration_plan.md（確定版・着手済み。進捗は kanban と memory を参照）— 関連作業の前に読む。フェーズ P0〜P7・置換テーブル草案・検証条件はここが正。
- 裁定済み: 公開リポジトリは ${REPO_NAME}_public（GitHub リポジトリ本体はユーザーが作成する）・h01 系 criteria も公開可（機密プロジェクトではない）・cron はそのまま配布。
- task_ambi_public は v2 専用リポジトリ — v3 用に流用しない。
- 役割名の一般化: project_lead の役割名・criteria ファイル名は `${PROJECT_<code>_NAME}` プレースホルダで一般化する（例: `project_lead_${PROJECT_G01_NAME}`・`criteria_project_lead_${PROJECT_G01_NAME}.md`）。`${ORG_NAME}` や実名の直書きに寄せない。
- 例外（2026-10-31 人間裁定）: カテゴリ名 `taskambi` は公開でもリテラル保持。F4 の `taskambi → ${PROJECT_NAME}` は廃止し、REVERSE_MAP・installer・engine の対応定義からも削除済み（三者を同時に更新しないと自己テストが失敗する）。
- 公開生成スクリプトと置換表は正本の `scripts/` 配下に置き、生成物リポジトリとは分離する。導入スクリプトの正本は `harness/install_local.sh`、許可リストの共通検証処理は `harness/skill_manifest.py`。公開側だけの手編集で終わらせない。

## references
- references/hermes-profile-distributions.md — export/import・distribution.yaml・install/update の動作とハード除外リスト
- references/clean-env-verification-run.md — クリーン環境での install スクリプト apply 検証（dry-run→fail-fast→スナップショット→承認ゲート→apply）の型
