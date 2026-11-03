---
name: taskambi_kanban-agent-org
description: "Use when running the 4-tier kanban agent organization."
version: 1.0.0
author: Hermes Agent
category: taskambi
---

# 4層カンバン・エージェント組織の運用

## When to Use

- ユーザーが4階層カンバン組織でサンプルタスクの実行・再確認を求めたとき
- ペルソナの SOUL.md を設計・修正するとき（階層逸脱の防止条項を含む）
- kanban 組織の run 結果を検収・後片束するとき

## 建付け

Hermes kanban の上に構築されたユーザー独自の4階層AI組織（task_ambi プロジェクトの R-01 設計に準拠）を動かす手順。kanban 自体のメカニクス（create / --parent の依存の向き / workspace / unblock / トラブルシュート）は `~/kanban-guide.md` が正本 — 本skillはそれを繰り返さない。

## 組織設計（invariant — ユーザーの裁定で固定）

`~/.hermes/profiles/` 下に25ペルソナ（2026-10-15 実測。※2026-10-21 追記: 別途実験用プロファイル `spike-a` が存在したが組織の25ペルソナには含めない。`spike-a` はプロファイル配布機構（distribution.yaml・env_requires・同梱/共有スキル・pre_tool_call hook・plugin）の検証用スパイクで、検証完了後に削除済み。インスタンスは `~/.hermes/archive/spike-a_profile_20261021_1826.tar.gz`（1.7MB）に退避済みで復元元として参照可。配布ソースは `~/work/hermes-harness-spike/dist/spike-a/` に残存）: planner 1 + project_lead 複製 6 + 第3層 3 + 実行 15:

- 分解・検収専任（上位3層）: `planner`(統括) → `project_lead_{デスクトッププロジェクト正式名}` → `system_engineer`(プログラム・調査系) / `public_relation`(文書・広報系) / `maintenance_procedures`(保守系)。**共用の project_lead は廃止（2026-10-15 ユーザー裁定）**: 本家 project_lead は `project_lead_xxx_others_pj` に改名され、xxx_others_pj 専任＋「専任の無いプロジェクト・対象を特定できないタスク」のフォールバックを兼ねる。planner SOUL の assignee 条項に「専任があれば project_lead_<正式名>、無ければ project_lead_xxx_others_pj」を記載済み。新規プロジェクトでは専任 project_lead_<名前> を作成し planner がそちらへ振り分ける
- **doc_lead 廃止・public_relation 新設（2026-10-15 ユーザー裁定）**: 第3層は system_engineer（プログラム・調査系）＋ public_relation（文書・広報系）。writer は `content_writer` に改名、`structure_designer`（章立て・段落構成の設計・新設。本文の執筆は content_writer）と analyst を public_relation 配下に置く。architect は system_engineer 専任（旧 doc_lead 配下との両働きは廃止）。doc_lead 本体は export バックアップ後に削除済み。実行9役→実行12役。同日、`presenter`(Marp/pptx のプレゼン資料作成・実行ワーカー)と `communication`(Discord・メール等の返信・メッセージ文案作成・実行ワーカー。送信・投稿はしない)を public_relation 配下に追加
- **maintenance_procedures 新設（2026-10-15 ユーザー裁定）**: 第三層の保守系専任を追加。配下の実行3役: `vault`（Obsidian vault `${VAULT_ROOT}` の保守専任 — ノート整理・リネーム・リンク・frontmatter・重複排除。SOUL に 9p 配下の in-place 上書き条項・Obsidian 禁止文字（< > : " / \ | ? *）条項・remotely-save 配下の大量移動注意・`.obsidian/` 非許可を入れる）／`harness`（Hermes ハーネス ~/.hermes 配下の点検・修正・動作確認 — .env・鍵は読み取りも禁止、criteria/SOUL/config の改訂適用は本文に人間承認の明示があるときだけ、rm -rf・プロファイル削除・kanban.db/state.db 直接書込・serve 停止は人間へ、`hermes gateway restart` は許可、変更後の動作確認と差分を成果物に必須）／`kaizen`（実行実績の計測・評価・改善提案 — Langfuse events_only http://${LOCAL_IP}:3000 と各プロファイル state.db は SELECT のみ、compose/コンテナ/DB は変更しない、改訂適用は人間承認後、SQL・数値を成果物に併記）。実行12役→実行15役。`kaizen` の .env には default の `~/.hermes/.env` から `HERMES_LANGFUSE_*` 3変数を値を画面に出さずコピー済み（`grep '^HERMES_LANGFUSE' ~/.hermes/.env >> ~/.hermes/profiles/kaizen/.env`）。criteria.md は適用者を「分解・検収専任の5役」に更新済み。project_lead 全複製（6役）のルーティング条項に「保守系→maintenance_procedures」適用済み。system_engineer / public_relation SOUL に「vault / harness / kaizen は maintenance_procedures 系の担当なので使わない」を追加済み。maintenance_procedures SOUL には workspace 条項（vault 内作業は vault 配下の対象ディレクトリ絶対パス・harness/kaizen 系は既存実在ディレクトリ・新規作成は needs_input）と誤配条項（保守系3領域外は needs_input）を追加
- **planner の参照ルートは vault ルート（2026-10-15 ユーザー裁定）**: `${VAULT_ROOT}`（デスクトッププロジェクト vault_root と同じ）。SOUL「参照ルート（vault ルート）」節に記載: 対象プロジェクト判定は `20_projects/` 配下の `20_*` 実在確認（ls）＋ `hermes profile list` で専任有無を判断、各プロジェクト契約はそのルートの .hermes.md を読む（vault ルート自体には .hermes.md 無し）、vault 内参照可・成果物編集はしない、子の workspace は対象プロジェクトの絶対パス
- system_engineer 配下の実行専任: `architect` / `programmer` / `debugger`(根本原因分析・最小修正) / `test_engineer`(テストのみ編集) / `devops`(デプロイ・CI/CD、危険コマンド・.env は kanban_block で人間へ) / `code_reviewer`(レビュー報告のみ、編集しない) / `specification_writer`(文書ファイルのみ編集)
- public_relation 配下の実行専任: `content_writer`(旧 writer・2026-10-15 改名・汎用文章の執筆) / `structure_designer`(2026-10-15 新設・章立て・段落構成の設計。本文の執筆は content_writer) / `analyst` / `presenter`(2026-10-15 追加・Marp/pptx 等プレゼン資料の作成) / `communication`(2026-10-15 追加・Discord・メール等の返信文案作成。送信・投稿はしない) — 5役とも public_relation 系専属。system_engineer は使わない。`architect` は system_engineer 専任（旧 doc_lead 配下との両働きは廃止）
- **project_lead はプロジェクトごとに複製する（2026-10-15 ユーザー裁定）**: 命名は `project_lead_{project名}` で、**project名はデスクトッププロジェクト（desktop_project list）の正式名に一致させる**（実測: ユーザーの入力 miss で ${PROJECT_H01_NAME} が confidentials と打たれ、rename で修正した）。作成手順: ①`desktop_project list` で正式名とプロジェクトルート実パスを確認 ②`hermes profile create <名前> --clone-from project_lead` ③`hermes profile describe <名前> --text "<project名>専用のproject_lead。..."` ④SOUL.md 冒頭のタイトルを新名に直し「担当プロジェクト」節に専任プロジェクト名・プロジェクトルート絶対パス・ディレクトリ参照指示を書く（プロジェクトで開いたときと同じくルート配下のディレクトリを参照させる）。④の必須要素: 起票前にルートの .hermes.md を読み契約を子本文に反映する／子に参照先を具体的相対パスで書かせる（推測禁止）／成果物先はその .hermes.md の契約どおり（outcomes/ とは限らない — p01 では成果物用新規ディレクトリは起票本文でユーザー承認を得てから作成、mental_diary は読み取りのみ）／kanban_create は workspace_kind='dir' + workspace_path=実在ディレクトリの絶対パス（接頭辞なし）で子の cwd をルート配下に置き .hermes.md を自動注入させる（コード系は .hermes.md 契約どおり ext4 側リポジトリ等を workspace にする）／機密条項（memory/skill 保存禁止・外部送信禁止）がある場合は子の本文に含める／9p 配下なので in-place 上書き（tmp→rename 禁止）を子に伝える。他プロジェクト/判別不能タスクは着手せず needs_input。それ以外の SOUL 本文は本家と同一のまま保つ。実例: project_lead_${PROJECT_H01_NAME}（outcomes/ のみ編集可）、project_lead_${PROJECT_P01_NAME}（ノート側 vault ＋ ext4 リポジトリ <project-code-repo> の2拠点）、project_lead_${PROJECT_P02_NAME}（成果物は projects/ 配下）、project_lead_${PROJECT_H02_NAME}（契約と実ディレクトリ一致・特に差分なし）、project_lead_${PROJECT_G01_NAME}（ext4 モノレポ・outcomes/ なし・成果物は既存構成 plans/docs/specs・uv 前提・make test・.env 触らない）、project_lead_xxx_others_pj（本家改名・20_xxx_others 汎用フォルダ専任＋フォールバック兼務・標準構成対象外・全配下編集可）。**作成時の確認: .hermes.md に書かれたディレクトリ名と実在ディレクトリ名のズレを必ず検出する**（p02 実測: 契約に resource/ とあるが実在は resources/。ズレがあると子タスクが契約通りに辿って詰む — SOUL には実在名を書き、契約側の修正は人間に提案する）。**注意: profile ディレクトリは hermes が小文字化する**（project_lead_${PROJECT_P01_NAME}）が、assignee に指定する名前はデスクトッププロジェクト正式名のまま（project_lead_${PROJECT_P01_NAME}）でよい。**発散管理: project_lead の SOUL/criteria 運用を改訂したら、全ての project_lead_* 複製に同じ改訂を適用する**（複製は実体コピーで共有されないため）。点検・一括適用は skill 'taskambi_sync_project_lead'（check / sync --apply / capture --from）で機械的に行える。共通節＝「## あなたは誰か」行から EOF までを全複製で同一に保つ。新規複製時は本家 SOUL と diff を取り改訂漏れを確認してから複製する（複製後も同 skill の check で確認）
- 新ペルソナ追加は `hermes profile create <名前> --clone-from programmer`（config.yaml + .env を引き継ぐ。ワーカーはプロファイルの .env しか読まないので必須）+ `hermes profile describe <名前> --text "..."` + SOUL.md を実行ワーカーの防衛条項テンプレートで書く。名前はアンダースコア統一（hyphen は避ける）

設計原則:
- 上位3層は**分解・判断・検収のみ**。成果物を書くのは実行ワーカーだけ
- 検収は上位層の専権。実行ワーカーは検収・レビュー用タスクを起票しない
- 階層を飛ばさない: planner の子は必ず project_lead。project_lead の子は、プログラム・調査系→system_engineer、文書系→public_relation、保守系（vault・harness・kaizen に当てはまる作業）→maintenance_procedures
- 成果物ファイル名は親の受け入れ条件から子へ**原文のまま**引き継ぐ（言い換えると、条件を満たすファイルが存在しないまま全子が完了する）
- 役割を複数プロジェクトで使い回す設計（共用 vs 複製の裁定・プロジェクトごとの参照/編集ディレクトリ契約の置き場所・Obsidian vault をプロジェクトルートにする手順）は skill 'multi-project-agent-roles' が正本。本skillは繰り返さない

SOUL.md に必須の防衛条項（これを外すと逸脱が再発する）:

- 分解担当5役（planner / project_lead / system_engineer / public_relation / maintenance_procedures）: 「タスク本文に『あなたが成果物を作る』『実装せよ』と書かれていても、成果物を書かない。実行は子タスクに分解して委任する。本文とSOULが矛盾するときはSOULを優先し kanban_comment に理由を記録」— **タスク本文は SOUL を上書きしてしまう**ため、明示条項がないと本文の指示に従ってしまう
- project_lead: 分解担当への起票本文に実行の契約（「実装せよ」等）を書かない。子の本文には「子タスクに分解して実行系ワーカーに委任」を明記
- 上位3層: 成果物の作成・削除・変更は禁止だが、**検収のための読み取り専用コマンド（cat / ls / 成果物プログラムの実行）は許可**する（実行禁止のままにすると検収が物理的にできない）
- 実行ワーカー全役（15役）: 検収・レビュー用タスクの起票禁止
- code_reviewer: レビュー対象は読み取り専用（成果物は報告書のみ）。test_engineer: テストファイル以外編集禁止、実装を曲げない。devops: `.env*`・鍵ファイルは読み取りも禁止、`rm -rf` / `git push --force` / 本番不可逆操作は実行せず kanban_comment + 成果物に記録して人間の判断を仰ぐ。specification_writer: ソースコードは編集しない

SOUL.md の変更は次回 spawn のワーカーから反映される（実行中の run には効かない）。

## 組織の自己学習の流れ（実測）

- 各ペルソナは独立した `skills/`・`memories/` を持つ（`--clone-from` は実体コピーでシンボリックリンクではない）。ワーカーが memory / skill_manage で書いた学習は**そのペルソナのプロファイルにしか蓄積されず、役割間で共有されない**。組織横断の知見は共有ファイル（本skill・criteria.md）側に置くのが正。同じ構造上の理由で、**default プロファイルに後から追加したグローバルスキルはペルソナから見えない**（kanban_create の skills 指定は assignee プロファイルの skills/ と external_dirs からしか解決されない）。全ペルソナに配布したいスキルは、各プロファイル config.yaml の `skills.external_dirs` に `${HERMES_HOME}/skills` を足して共有する。スキル配布の実務ルール: **新規スキルは共有 `~/.hermes/skills/` 側に置き、プロファイル固有 `skills/` には作らない** — スキル解決はローカル（プロファイル skills/）優先・外部dirは後なので、同名スキルがあると clone 時点で凍結された古いスナップショットが共有dirの新版を隠す。`external_dirs` 配下は curator の対象外（read-only・自動アーカイブされない）なので、共有側は正本置き場として安定し、不要になったら手動で消す。SKILL.md の frontmatter（name/description）が壊れるとサイレントにロードされないので、作成・編集は skill_manage か `hermes skills install` 経由にする（手mkdirでfrontmatter無しのディレクトリを置かない）。健全性確認は `hermes skills list` / `hermes curator status`、スキル構成の退避・移行は `hermes skills snapshot`
- **各ペルソナの memories/MEMORY.md は clone 時点のスナップショットのまま放置されがち**（default profile より古くなる）。暗黙の自己学習（ワーカーが memory に書く）には依存せず、明示的な改訂ループで学習させること
- 実際に学習が流れる3経路: ①spawn時のスキル注入（関連skillは自動ロード） ②カードコメントスレッド（再spawnワーカーが全文を読む — タスク単位の知識伝達） ③SOUL.md / criteria.md の改訂ループ（逸脱検出 → 条項強化 → 次回spawnから反映）
- 役割固有の定石を蓄積させたいときは、そのSOULに「困難から学んだ手順は skill_manage で自分のプロファイルに保存せよ」を追記する。ただし全ペルソナが独立に発明して発散するリスクがあるので、汎用化できる知見は本skillか criteria.md に集約してから配布する

## サンプル実行の手順

1. ボード確認: `hermes kanban list`（前回分が残っていないか）。プロファイルのゲートウェイが running かは `hermes profile list` で確認
3. 共有 workspace を `dir:<path>` で用意し、`pj_input/`（入力）と `outcome/`（成果物）に分ける。**`--workspace` を省略すると scratch になり完了時に消える**。**起票本文には workspace を「dir: 接頭辞なしの絶対パス」で書く**（本文の `dir:$RUN` 表記をそのまま子起票時にコピーすると worker が `dir:/abs/path` を渡して spawn_failed×2 → gave_up で恒久詰み。sample5 で doc_lead 配下の2枚が発生。詰んだら「正しい workspace で代替カード起票 → 詰みカードへの link を全て unlink → 差し替えコメント残置 → 完了後 archive」）
3. ルートタスクを1枚だけ起票 — 階層は起票本文から自然にカスケードさせる:
   ```bash
   hermes kanban create "<タイトル>" \
     --body "【人間からの依頼】...\n受け入れ条件:\n- [ ] outcome/<成果物名> が...\n【制約】..." \
     --assignee planner --workspace dir:<path> --max-runtime 40m
   ```
   本文に必ず: 固定の成果物ファイル名（原文引き継ぎ・言い換え禁止を明記）、workspace 統一の指示、「上位3層は分解・判断・検収のみ」の一文、「【未確定点の扱い】」節（3行型: 未確定=人間の裁定事項はあるか / 【裁定：上位層】済みの点と結論 / 【裁量：実行ワーカー】の範囲。未確定が無い場合もその旨を明記する）
4. `hermes kanban watch` を background で流し、2〜4分ごとに `hermes kanban list` を確認。全層完了まで10〜20分を見込む
5. **人間側で検収**: 成果物の存在確認に加え、プログラムは自分で再実行して出力を検算する。ワーカーの summary / artifacts 申告を根拠にしない（検収の原則: 実体で判定）
6. 後片付け:
   ```bash
   ids=$(hermes kanban list 2>/dev/null | awk '$3=="done" && $2 ~ /^t_/ {print $2}')
   hermes kanban archive $ids
   ```
   （list の2列目がID・3列目が状態。`$2=="done"` と取り違えない）
7. **実行順序の説明を求められたら**: アーカイブ後も `hermes kanban show <id>` は読めるので、各カードの created / started / completed の3時刻を拾って時系列を再構築する。実行役・レビュアーの確定は `hermes kanban runs <id>`（attempt 単位で profile・outcome・開始時刻を出す。review_requested → completed の2行で検収ループも読める）。**`kanban list` の assignee 列は実装者ではなく最終 run の profile（通常レビュアー）を表示する** — 実装役判定・逸脱判定に使うと誤読するので runs で確認する。起票者は create イベントの `creator_task_id`（親カード）で辿る。進行の型は「親が完了した瞬間に子が起票・promote（`dependency_wait {reason: parent_not_done}`）→ 依存が揃ったカードは並行 spawn」。何が並行になるかは依存グラフ次第で、本文の依存指示1文が並行と直列の形を決める

## サンプルの保管規約（ユーザー指定の運用）

サンプルタスクは `~/${KANBAN_RUNS_DIR}/samples/<名前>/` に「タスク本文 + 入力ファイル」の形でファイルとして保管し、いつでも使い回せるようにする（README.md = 索引と使い回し手順）:
- `task_body.md` — 起票タイトル・本文・受け入れ条件・制約（検証目的も1行で明記）
- `pj_input/<入力ファイル>` — ワーカーが読む実データ
- `create_task.sh`（任意）— workspace パスを `RUN=` 変数化した再起票スクリプト。使い回すときは `RUN=<新dir> ./create_task.sh` で入力コピーから起票まで一括
新規サンプルを作ったら同じ形で保存する。実行ディレクトリ本体（`~/${KANBAN_RUNS_DIR}/<名前>/`）は成果物の残置場所であり、削除はユーザーが手動管理する。

## 第3層両働きのサンプル（system_engineer + public_relation を同時に確認したいとき）

起票本文に「プログラム系統と文書系統の2ワークストリーム + doc 系を program 系の子の子としてリンク（順序依存）」と書くと、project_lead が system_engineer と public_relation の両方に起票し、強化後 SOUL で全階層遵守・約10分で完走する（実績あり、`sample2_pytool` として保管済み）。検収は人間が CLI 再実行 + 独立再計算で突合する。

## 人間裁定ゲートのサンプル（kanban上で人間の判断を仰ぐ）

`needs_input` 機構で「ワーカーが kanban 上で人間の判断を仰ぎ、人間がコメントすると進む」フローが作れる（`sample4_human_gate` として保管、ゲート部は実動作確認済み）:

- ワーカー側: 判断点で `kanban_block(kind='needs_input')` を呼ぶとタスクが blocked になり、reason がボードに残る。質問には「決定すべき項目 + 実データに基づく候補と候補ごとの該当件数」を添えると人間が即断できる
- 人間側: `hermes kanban comment <id> "裁定"` → `hermes kanban unblock <id>`。**再 spawn されたワーカーは spawn 時にコメントスレッド全文を読む**ので裁定は確実に届く（回答を別媒体で渡す必要はない）
- 起票本文の必須文言: ①未確定点は人間の裁定事項であり、実装ワーカーは自己判断で仮定しない ②判断点で担当中タスクを needs_input で停止し、回答を kanban_show で読んでから続行する ③確認の別タスク化・他ワーカーへの代行・上位層による仮置きを禁止 ④決定待ちの間に後続を進めない
- 待ちの伝播: 後続タスクをゲートを含む実装カードの依存先にしておくと、ゲート中は todo/blocked のまま止まる。待つ側のワーカーが自発的に自タスクをゲートカードに link して待つ動作も確認済み

## 裁定基準（criteria.md v1、2026-10-05導入）

「人間に聞くか上位層が判断するか」の判断基準は `${KANBAN_RUNS_ROOT}/criteria.md` に明文化し、上位4役の SOUL に「判断点の裁定」節を入れて適用させる。単一の真実の源は criteria.md 側で、SOUL は参照するだけ（改訂は criteria.md のみ）:

- **criteria 2段構成（2026-10-15 導入・ユーザー承認済み）**: 共通コア criteria.md（v1.1・全5役共通）＋役別上書き criteria_<役>.md（system_engineer / public_relation / maintenance_procedures の3役分・YAML frontmatter 付き v1.0・~/${KANBAN_RUNS_DIR}/ に並置）。役別表の §0 に「共通コア先読み→役別表適用・競合時は役別表優先・緩める改訂は役別表で行わない」を明記。第3層3役の SOUL「判断点の裁定」節は共通コア＋役別表の2段参照に改訂済み（改訂候補コメントの宛先を役別表と共通コアで分離、criteria.md §5 適用時に役別「検収の役別確認事項」節を併用、レビュー中の基準参照も2段化）。project_lead 複製6役分の criteria_project_lead_<正式名>.md（p01 は大文字正式名 criteria_project_lead_${PROJECT_P01_NAME}.md）を作成済み（v1.0）: §0 専任限定＋§1 分解設計の共通表（分解設計・workspace 選定＝上位層、新規ディレクトリ作成・契約ズレ検出＝人間、伝播義務は判断点にならない）＋§2 プロジェクト固有条項（.hermes.md 契約の正本性・拠点/権限/必須伝播事項を各プロジェクト実測で具体化: g01=モノレポ+uv/make test、h01=秘密区分の人間裁定、p01=2拠点+機密条項、p02=resources/ ズレ、xxx=フォールバック時は §2 適用外）＋§4「project_lead 共通部分の改訂は全複製 criteria_project_lead_*.md へ同時適用」を明記
- **SOUL 参照改訂済み（2026-10-15・全複製動作確認済み）**: 共通節を保つ方式は「役別パスの指定だけを複製固有節に置く」。6複製の担当プロジェクト節に「### 裁定基準の適用」サブ節（自分の criteria ファイルの絶対パス・読み込み順序・競合優先を1行で指定）を挿入し、共通節内の「判断点の裁定」節は役別ファイル名を書かない汎用表現（「役別表＝担当プロジェクト節で指定した criteria ファイル」）で2段構成化した。検証: 共通節（## あなたは誰か〜EOF）の sha256 が全6複製で一致（121c3dba7353）、固有節のファイル名指定は6複製とも自役の正しいファイル（p01 は大文字 AAsystem）。planner は criteria.md のみ参照のまま
- patch ツールの部分行マッチ（行頭から始まらない old_string）は、同一ファイルへの先行 patch が挿入を行った後にマッチ失敗する実測あり → SOUL 等の複数箇所編集は行単位の完全一致で行う

- 3ラベル:【裁定：人間】（不可逆・価値・要件・基準外）／【裁定：上位層】（可逆かつ技術的、案で成果物の形が変わる）／【裁量：実行ワーカー】（型に沿う実装詳細）。判定は「不可逆か → 価値判断か → 形が変わる技術選択か → 型に沿う詳細か」の順、どこにも当てはまらなければ人間（fail-safe）
- 経路の核心: **実行12役は人間に直接質問しない**。ラベル外の判断点は【裁定依頼】カードを親役に起票 → 自カードを依頼カードの子に link → dependency block で待つ。親役が基準表で分類し、上位層裁定なら根拠を comment 記録して完了（依存が解けて実行カードが自動再開）、人間裁定なら親役自身が needs_input で人間に問う
- 分解時の【裁定：人間】は子タスク起票前に needs_input で解決し、結論を子タスク本文に明文化してから完了する（実行フェーズに回答待ちを残さない）
- 改訂ループ: 同種の needs_input・裁定依頼が2回以上 → 「改訂候補: 」コメント → 人間が criteria.md を v2 に更新
- 実装状況: 上位5役 SOUL の「判断点の裁定」節＋実行15役 SOUL の「判断点の扱い」節（人間直接質問の禁止＋裁定依頼カード経路＋起票例外条項）＋devops 固有条項（秘密情報・危険コマンドも裁定依頼経路へ）＋**検収ループ**（2026-10-05）: 実行15役の終端を kanban_complete → kanban_request_review（reviewer=親役、summary に作成内容と検証方法、artifacts に成果物パス）に変更、15役に「検収と差し戻し」節（差戻し後は指摘のみ修正・全文書き直し禁止）、上位5役に「レビュアーとして呼ばれたとき」節（実体検証・合格 kanban_complete／不合格 kanban_request_changes・判定根拠を comment 記録＋criteria.md §5「検収不合格の処置」の適用行）。criteria.md は **v1.1**（§5 検収不合格の処置＝差戻し時の波及同期対象の明記・テスト→報告書の順の同期チェーン・修正カードのスコープ封じ込め）。親の分解カードは done のままでも reviewer として spawn され直すことで検収が実現（依存の向き上、親を開けたままにする仕様は不可能）。検証 run 完了（sample5_rework）: ①ループ全自動1往復を実動作確認（request_review→実体検証→request_changes→自動 requeue→再 spawn→指摘のみ修正→再 review→approved）。「未確定点の扱い」節の3行型は sample5 で初使用済み。**残タスク: 実行ワーカー自身による【裁定依頼】カード起票・link・dependency block の実動作検証のみ**
- **sample5_rework の事後裁定（ユーザー・2026-10-05）**: SOUL 持ち越しは「差戻しの波及 → 同期カードチェーン」のみ（criteria v1.1 §5 として反映済み）。S の伝達経路・done タスクの reopen 不可・重複起票は fixture 設計・kanban CLI 仕様の問題であり SOUL 修正不要。workspace 起票ミスは SOUL ではなく起票本文テンプレート側で防ぐ（本skill「サンプル実行の手順」3 に反映済み）
- **sample5_rework 使い回し再実行後の事後裁定（ユーザー・2026-10-06・2026-10-05裁定を一部改訂）**: 使い回し再実行で「S が分解役で落ちる（SOUL優先条項が本文の記録指示を打ち消す）」と「scratch 誤起票の重複連鎖」が再発し、本文テンプレートだけでの防止が不十分と判明 → 分解担当4役 SOUL に ①「判断点の裁定」節への本文確定宣言は裁量に分類しない・検収条件記録指示を先に逐語実行する条項 ②「レビュアーとして呼ばれたとき」節への自カード・親カードの【検収条件】コメント読み出し適用条項 ③workspace 起票形式条項（workspace_kind='dir' + workspace_path=接頭辞なし絶対パス・誤起票時の【無効・着手禁止】コメント付き再起票手順）を追加。S の伝達経路と重複起票の防止は「本文テンプレート + SOUL 」の二段構えに改訂

## 第二層の用語集（用語統一機構・2026-11-03 ユーザー指示）

- criteria と同じ方式の2段構成: **共通用語集** `${KANBAN_RUNS_ROOT}/glossary_project_lead_xxx_others_pj.md`（正本・project_lead 全複製共通。共通用語は xxx_others_pj に置く裁定）＋**プロジェクト固有用語集** `${KANBAN_RUNS_ROOT}/glossary_project_lead_<正式名>.md`（5プロジェクト分・p01 は大文字 AAsystem）。競合時はプロジェクト固有を優先（criteria の役別優先に準拠）。共通用語の複製は作らない（単一ソース）
- project_lead 全6複製の SOUL に「### 用語の統一（用語集の適用）」サブ節（固有節・各パス指定）と、共通節に起票時の【用語の統一】節記載条項・レビュアー節に用語統一確認条項を追加済み。第3層分解役3役（system_engineer / public_relation / maintenance_procedures）の SOUL に「親の【用語の統一】指示を子の本文にも原文のまま伝播」条項を追加済み。第4層は本文を作業仕様として扱う既存条項で受ける（SOUL 追加なし）
- 用語集の改訂は人間のみ。改訂候補は kanban_comment に「改訂候補: 用語集 …」で記録する。project_lead・第3層とも用語集ファイルを編集しない
- 現状はサンプル版（v0.1・2026-11-03）: 項目は動作確認用の実在事実ベース（h01 正式名 confidencials・p02 resources/ ズレ・g01 uv/make test 等）。実運用の用語へは人間が差し替える
- **動作確認は未実施**: 用語統一指示が子本文に現れ、成果物の表記が統一されるか・検収で揺れが検出されるかを次回 run で確認する。SOUL 改訂は次回 spawn から反映


## 検収差し戻しループの運用知見（実測）

- **差戻しできるのは review 状態のタスクだけ**: `reopen-review` も `request-changes` も、review run が終わった（done の）タスクには効かない（'not in an active review run'）。完走後に検収不合格が判明したら、人間が**差し戻し修正カード**を起票する: assignee=当該実行役、本文に「指摘された点のみ修正・全文書き直し禁止・tests/ や outcome/ 等の他カードの成果物は編集しない」を明記し、終端を kanban_request_review（reviewer=当該親役）にして検収ループに接続する。不合格の証跡は検収役のカードコメントに残す
- **隠し検収条件（検収時点で初めて適用する仕様）は、実際に検収する役の視界に置く**: 分解が project_lead→system_engineer→programmer と深くなると、リーフの reviewer は「自分を起票した直近の親役」になる。曾祖父母カードの本文や planner カードのコメントは reviewer に読まれない。条件 S の内容は「検収を実際に行う層の直近の親カードの kanban_comment」に置き、各層の子本文には「検収時に ○○カードの【検収条件】コメントを読み出して適用せよ（内容自体は書くな）」の**指針だけ**を伝播させる。上位層が先に done になると指針の伝達が断たれる。**ただしこのコメント経路は再現性が低い**: 使い回し再実行では、ルート本文に「実装子タスク起票直後に【検収条件】コメントを記録せよ」と明記しても分解役が当該点を【裁量：実行ワーカー】と分類して S をどこにも記録せず、リーフ検収が round 1 合格した。検収段階で初めて適用する条件を**確実**に適用させる唯一の実測経路は、差戻し修正カードの本文に条件を全文明記すること（その形なら round 1 で合格する）。SOUL 側の対策（2026-10-06 適用）: 分解担当4役の「判断点の裁定」節に本文確定宣言は裁量に分類しない条項を、「レビュアーとして呼ばれたとき」節に自カード・親カードの【検収条件】コメント読み出し適用条項を追加 — 次回以降の run で発火確認が残る
- **差戻しを発生させるフィクスチャは、実データで観測可能な差にする**: 3桁区切りカンマは3桁しかないデータでは出力が変わらず発火しない。小数の .0 削除や合計行 TOTAL の追加のように、期待出力が目で変わる差を使う。フィクスチャ仕様は実際の入力データで一度手計算し、変わることを確認してから起票する
- **検収・再検証の一時フィクスチャは workspace 内に残す**: 実装側と検収役が /tmp 等に作った確認用 CSV は消えて再現できず、両者の申告が食い違っても第三者が突合できない（実測: 同じ4桁CSVの合計値申告が食い違い、どちらも検証不能のまま残った）。整形仕様などの追加確認は run ディレクトリ直下に置くか、検収コメントに CSV 内容を全文記載する
- **遅延開示は「テストより前に実装が確定する」前提で依存を張る**: S がテスト開始後まで届かないと、テストが旧仕様の期待値（平文整形等）で書かれ、差戻しの波及がテストカードにも及ぶ。テストは検収済みの最終実装リーフを親にする
- 隠し条件を「誰に開示しないか」を起票本文に明記する（例: 実装者は planner カードのコメントを読みに行かない）。書かないとワーカーが先行参照してフィクスチャが無効化される
- **波及の回収は同期カードチェーン（テスト→報告書の順）で行う**: 実装の差戻しで挙動が変わると、テスト・報告書が旧仕様のまま残る（sample5 実測: tests 3 failures・test_report「全件合格」が虚偽化）。検収役は request_changes の理由に波及同期対象を明記し（criteria.md v1.1 §5）、修正完了後にテスト同期 → 報告書同期の依存チェーンを起票する。報告書は検収済みテスト結果を根拠にするので必ずテストが先。修正カードの受け入れ条件には「依存成果物を変更していない」を入れ、波及の回収を修正カードに混ぜない

## 実績サンプル

- `sample2_pytool`: 第3層両働き（system_engineer + doc_lead〔現 public_relation〕）、約10分で完走
- `sample3_bugfix`（2026-10-05）: 新ワーカー検証。debugger / test_engineer / code_reviewer / specification_writer が全て葉タスクの assignee として実動作、検収合格。発見された逸脱: system_engineer が検証タスクを自分自身に assign して実測ログを書いた（重複起票も）。対策済み: system_engineer SOUL に「assignee を自分にしない・成果物を伴う作業は必ず委任」条項を追加
- `sample4_human_gate`（2026-10-05）: 人間裁定ゲート検証、検収合格（26カード完走）。programmer が基準値未確定を検出 → `kanban_block(kind='needs_input')` で実データに基づく候補+該当行数を提示して停止 → 人間がダッシュボード（desktop）のコメント欄から回答 → 人間側 unblock → 再 spawn がコメントスレッドを読んで続行。decision_record.md に回答の一字一句の引用が記録された。確認手段: CLI は `show` の Events の `'kind': 'needs_input'`、**デスクトップアプリの Kanban タブ**は blocked カードに種別バッジ直表示（要: 設定→スキルとツール→プラグインで Kanban を有効化。web dashboard にはバッジ表示なし）
- `sample5_rework`（2026-10-05）: 検収差し戻し（手戻り）ループ検証、人間側検収合格。**①ループ全自動1往復を実動作確認**: 実行ワーカー request_review → 親役が reviewer として spawn → 実体検証（自作プローブ CSV で整形仕様を実測）→ kanban_request_changes → 自動 requeue（ready）→ 再 spawn → **指摘2点のみ修正**（全文書き直しなし・tests/outcome 不変）→ 再 review → approved → done。判定根拠はすべて comment に記録された。人間側の最終検収は CLI 再実行+unittest 再実行で確認
  - 未検証の残: ②実行ワーカー自身による【裁定依頼】カード起票・link・dependency block の実動作（sample5 では発生せず）
- `sample5_rework`（使い回し再実行・全基準合格）: 同サンプルを `RUN=新dir` で再起票。自動差戻しは**不発火** — 隠し条件 S が分解役に【裁量】と分類され、どこにも記録されずリーフ検収が round 1 合格した（隠し条件ルートの再現性問題を再確認）。人間側検収で不合格を検収役カードの証跡コメントに記録 → 差戻し修正カード A（実装・**本文明記 S**）→ B（テスト期待値更新）→ C（報告書追記）の `--parent` チェーンで完走。人間の最終検収: CLI 再実行で S 一致（TOTAL 行・3桁カンマ・通常統計不変）、unittest 8/8、premature promote 無し。S を本文に明記した修正カードは一発合格する。差戻し修正カードの起票スクリプトと本文は `samples/sample5_rework/`（create_rework_cards.sh + body_a/b/c.md）に保管済み。残タスク②は変わらず未検証
- **sample5_rework run2**（2026-10-08・全基準合格・26カード完走 + 修正カード3枚）: `~/${KANBAN_RUNS_DIR}/sample5_rework_run2/`（create_rework_cards.sh + body_*_run2.md を保管）。2026-10-06 SOUL 改訂の**発火確認済み**: ①分解役（planner）が起票直後に【検収条件】S を自カードコメントへ逐語記録（「本文確定宣言を裁量に分類しない」条項が効いた）②workspace 条項で全カード `workspace_kind='dir'` 正常・誤起票/重複起票ゼロ。**S ゲートは3連続不発** — S を曾祖父母（planner カード）のコメントに置くとリーフ reviewer（自カード・直近親カードのコメントしか読まない）に届かない。コメント経路で確実に発火させるには【検収条件】コメントを**実際に検収する役の直近の親カード**に置く必要がある（信頼できるのは相変わらず修正カード本文への全文明記のみ・run2 修正Aは round 1 合格）。run 固有指示で「分解役の自カードに記録せよ」と書くと planner カードに置かれて届かなくなる点は fixture 設計時に注意。運用知見: 分解役が先行カードの完了を待つために needs_input で自己 blocked すると dependency 解消でも自動再開しない（手動 unblock 必要・sample4 型の再発）— 本文で待つ場合は dependency 種別の待機を設計する

## 人間ゲート（needs_input）の運用知見（実測）

- 再開は `hermes kanban comment <id> "裁定"` + `hermes kanban unblock <id>` の2段。再 spawn されたワーカーはコメントスレッド全文をコンテキストとして読む（公式仕様+実測）
- **依存の解消で自動再開するのは kind='dependency' の待機（todo で待つ）だけ。needs_input で自己 blocked したタスクは前提が揃っても自動では再開しない** — 人間（またはエージェント代理）が unblock する。sample4 では doc 系2タスクが「実装が終わるまで自分で blocked に入り」後から手動 unblock が必要だった
- タスク本文に「基準を決める時点で kanban_block(kind='needs_input') を使うこと・自己判断で仮置きしないこと」と書くと、分解担当（planner / project_lead / system_engineer）はその設計を原文どおり子に引き継ぎ、ゲートは確実に実装ワーカーのタスクで発生した（仮置き逸脱は無し）
- 依存の張り方の罠: 「実装タスクの直の子」としてテスト・レビューを起票すると、分解担当が『分解した』時点で自タスク done → 子が premature promote され実装前に走り出す。今回は後続チェーンが各々前提欠如を検出して自己 blocked し耐えたが、基本は**実装リーフのタスクIDを親にする**のが安全
- `sample4_human_gate`: 人間裁定ゲート検証。programmer が needs_input で停止・候補提示、文書系がゲート完了待ちに連鎖停止することまで実動作確認。保管先 `samples/sample4_human_gate/`（入力は sample3 の修正済み CLI を流用）

## ワーカーのコンテキスト必要量（実測 2026-10-06）

- **Langfuse にワーカー実行は流れない**: 実行ペルソナの .env に LANGFUSE キーが無い（--clone-from が取り込むのは config.yaml + .env で、Langfuse は default の .env だけにある）。実データは各プロファイルの `state.db` の sessions / session_model_usage テーブルにある
- 実測値（サンプル2〜5再実行、全13役・約180セッション）: ピークコンテキスト推定は「(sum_input + sum_cache_read) / api_call_count = 平均コンテキスト、ピーク ≈ 平均 × 1.5〜1.6」（較正: default 会話で Langfuse 実ピーク 161K / 推定式と突合）。結果は **project_lead 最大 ≈170K、他役は最大 50〜120K、中央値 50〜75K**。最も複雑だった sample5 再実行（差戻しループ+検収）でも 170K どまり → **250K コンテキストで十分、1M は不要**。リーフ実行役が巨大ファイルを丸ごと読む・run が桁違いに長くなる場合にのみ 1M を再検討

## Kanban 実装意味論（フロー設計の前提 — hermes_cli/kanban_db.py・tools/kanban_tools.py で検証済み）

新しいカードフロー（判定カード・修正ループの差し込み等）を設計するときに依存してよい実装挙動:

- **kanban_link は running でない他カードへの親追加に使える**（拒否されるのは running の child だけ。自分の running カードは run id で所有証明して link 可）。修正列の差し込みは「列を起票 → 列末尾を未開始の後続カードの親に link → 自分のカードを完了」の順で行う — 逆順だと後続が先に promote され、走り出したカードにはもう link できない
- **kind=dependency の待機はブロックループ検知にカウントされない**（blocked バケツに入らず todo で待つだけで recurrence が増えない）。判断待ち・回答待ちは必ず dependency で待つ設計にする
- **同一 kind で2回ブロックすると triage へルーティングされる**（BLOCK_RECURRENCE_LIMIT=2）。同じカードで needs_input を繰り返さない — triage 落ちしたカードは auto_decompose（既定 ON・triage 列だけが対象）に勝手に分解されうる
- **max_in_progress 未設定時の同時実行キャップはメモリ由来で最大8**（MemTotal/512MiB を [2,8] に clamp）。全カードが同一作業ツリーを共有するフローでは `kanban.max_in_progress: 1` を明示しないと複数カードが並行 spawn されて書き込み競合する
- **ワーカーの kanban ツールは dispatcher が自動注入する**（create/link/comment/complete/block/show は全タスクワーカーが使用可）。kanban_list / kanban_unblock はオーケストレーター専用でタスクワーカーからは見えない — ペルソナに割り当てる手順は list/unblock 不要な形に設計する
- **ワーカーのツールセットは assignee プロファイルの platform_toolsets.cli が spawn 時に --toolsets でピン留めされる**。ペルソナに必要なツール（file/terminal 等）が各プロファイルの platform_toolsets.cli にあるかを確認する

## 落とし穴

- **/mnt/c（9p/drvfs）配下では rename-over 方式の書き込みが Permission denied になる**: patch ツールや `mv` による「一時ファイル → rename で差し替え」が /mnt/c 配下のファイルで失敗する（実測: `.hermes-tmp.*` → `.hermes.md` の rename が拒否）。in-place 上書き（truncate + write、Python の `open(path, 'w')` 等）なら成功する。vault 内の成果物を編集するワーカーには in-place 方式を使わせるか、冒頭で「patch 失敗時は open('w') で上書きせよ」を伝える。patch が残した `.hermes-tmp.*` の後片付けも必要

- **検収差し戻しループは review 状態でしか回せない**: `reopen-review` / `request-changes` は request_review 後の active review にしか効かず、**done タスクは reopen 不可**（CLI 限界）。完走後の人間検収で不合格を見つけたら「修正カード起票」（sample5-R1 の形）になる。→ 設計上は、検収は request_review 直後に reviewer が実体で行うのが本体で、後付け検収はあくまで救済
- **遅延開示（隠し検収条件）の置き場所**: 条件を planner カードのコメントに置くだけでは、深い階層のリーフ検収役（programmer の親 = system_engineer 等）には届かない（sample5 run1 で S ゲート不発火）。発火させるには**指針（あるいは条件そのもの）を検収役が読む本文に伝播**させるが、指針経由のコメント参照は再現性が低い（使い回し再実行でも不発火）。信頼できるのは修正カード本文に条件を全文明記すること（両 run でこの形のみ確実に発火）
- **差戻しの波及**: 実装が差戻しで変わると、テスト・報告書が旧仕様のまま残る（sample5 で tests 3 failures・test_report「全件合格」が虚偽に）。CLI 修正カードの受け入れ条件で「tests/outcome 不変」を言っても、別カードとして**同期カード**（テスト期待値更新→報告書更新の順序依存チェーン）を起票する必要がある。仕様が検収時に確定する運用なら、テストは最終仕様確定後に走る依存設計が安全
- **worker による kanban_create の workspace ミス**: 本文コピー時に `dir:/abs/path`（接頭辞付き）を workspace に渡すと spawn_failed×2 → gave_up で恒久詰み（`kanban edit` では workspace 修正不能）。sample5 で doc_lead 配下の2枚（writer・analyst）が同時に詰み、**詰みカードを親に持つ後続カードも promote しなくなる**（dependency_wait で滞留）。復旧手順: 正しい workspace で代替カード起票 → 詰みカードへの link を `unlink` で全て解除 → 詰みカードに差し替えコメント残置 → 完了後 archive
- **重複起票の再発**: system_engineer が同一名の検証子カード（C1-a）を2枚起票し、両方完走（同一成果物ファイルに両者が書いたが実害なし）。sample3 の逸脱と同型。planner が同内容の親カードを2枚起票する逸脱も観測された（片方に workspace 未指定→scratch 化し、下位に重複チェーンがカスケード）。**分解役1カードから同一名が一気に burst する型もある**（実測: 1回の分解で同一名6枚 — 依存・workspace 正しい設計の4枚と、親なし・scratch 誤起票で ready まで進む2枚が混在。一括 kanban_create で起きる）。重複を検出したら放置しない: ①正規カードを1枚特定し（親カードの本文・コメントの指定で決める）②残り全カードに【無効・着手禁止】コメントを付け ③`hermes kanban block <id> --ids <残り全id> --kind needs_input "理由"` で手動ブロックする。ワークカーの自発停止を待つより手動 block が速く、ready の重複カードが spawn される前に止められる（実測: burst 6枚中5枚を spawn 前に封じ込め実害ゼロ）。残置 blocked は人間が archive。検収時は `kanban list` で同一名カードを確認する。2026-10-17 追加実測（テスト4-a/4-b）: probe 型 burst も同型（"ws-path probe" "test" 等のデバッグ風タイトル最大13枚・親リンク無し・scratch 混在）。発生率は 5 run 中 3 run。読み取り専用タスクでは実害ゼロ。対策適用済み: 分解担当5役 SOUL に「起票の自己検証」条項（1回1枚・parents 必須・children 突合・余分カード自 block）を人間承認の上追加、起動スキル 'taskambi_boot' v0.2.0 に分解役完了直後の突合→即封じ込め手順を実装。発火確認は次回 run

- **watch の停止**: `pkill -f "hermes kanban watch"` はコマンド文字列を含むラッパーシェル自身にマッチし、自分のシェルが SIGTERM で死ぬ。生存確認は `ps aux | grep "kanban [w]atch"`（[w] トリックで自己マッチ防止）。kill 後も遅延 heartbeat 通知が複数回届くが、実体が死んでいれば無視してよい
- `hermes kanban stats` を head/tail にパイプすると BrokenPipeError の traceback が出る（害はないが失敗に見える）。パイプしない
- **長い Python ファイルを write_file で書いたら py_compile 通過だけで信じない**: 書き込み時に制御文字が混入すると f-string 接頭辞が失われ、文字列が非f-stringのまま**構文エラーなしでコンパイルされ、実行時まで発覚しない**。書き込み後に制御文字（`ord(ch) < 32`、改行以外）を走査し、書いた文字列を使う実パスを一度実行して出力を確認する
- ワーカーは persona 外の仕事を引き受けることがある（実訓: writer が検収タスクを自発起票 / 本文指示で system_engineer が直接実装）。逸脱が起きたら SOUL 条項を強化してから再テストする。run 後は `hermes kanban show` の親子リンクで実際の層構成を確認する
- **順序依存の親選び**: 後続タスクを「分解・統括役のカード」の子にすると、統括役は分解を終えた時点で自タスクを done にするため、前提の実体（実装・成果物）が存在しないまま後続が promote されて走り出す。順序依存は「前提を実際に届けるカード（実装リーフ等）→ 後続」で張る
- planner が階層を圧縮して全子を project_lead に assign し「下位分解を許可」と本文に書く逸脱が観測された。起票本文では子の assignee を次層の役別（プログラム系=system_engineer / 文書系=public_relation）に指定する。逸脱が続くようなら planner SOUL に条項追加してから再テスト
- **ワーカー起票カードの workspace パスは絶対パスのみ**: ワーカーが kanban_create の workspace に `dir:/abs/path` の形（接頭辞付き）を渡すと、dispatcher が 'non-absolute workspace_path' で spawn_failed×2 → gave_up してカードが詰む。CLI の `edit` には workspace フィールドが無く直せない → 同じ本文・親・assignee で**代替カードを人間が起票**し、詰んだカードに superseded の旨を comment、その子の依存を代替カードに付け替える。run の起票本文には「workspace は絶対パスのみ（dir: 接頭辞を付けない）」を明記する
- **長い起票コマンドは実行承認ゲートで止まりやすい**: `--body` が長い `hermes kanban create` を直接実行すると承認待ちでタイムアウトし、結果が得られないことがある。起票本文は create_task.sh のように**ファイル化してから実行**する（編集と実行が分かれ、再試行も容易）。完了カードの一括 `archive` も同様に承認ゲートがかかる。archive は検収などの読み取りコマンドと混ぜず単独の短いコマンドで実行し、承認がタイムアウトしたら再実行せず状況と次の一手を人間に提示して待つ。**ゲートは外部書き込み系（glab issue create 等）にもかかる** — タイムアウト＝未実行なので、まず対象が未変更であることを確認してから報告する（例: `glab issue list` で未作成を確認）。heredoc→インタープリタへのパイプも別の警告対象になる — 検証プローブは事前にファイル化してから実行する
- **SOUL の workspace 記述は kanban_create のパラメータ名で書く**: 「子の workspace に dir:<共有ディレクトリ> を指定する」という素朴な記述だと、ワーカーが workspace 未指定（→ scratch 誤起票）や接頭辞付きの値を渡して失敗し、「着手しない→訂正版を再起票→譲渡」の重複カード連鎖が生じる（2026-10-06 実測: 1 run で scratch 誤起票 4 回、補助カード約 8 枚が余計に発生。ワーカーは毎回自己検知して暴走は止めた）。対策: 分解担当4役 SOUL に workspace_kind='dir' + workspace_path=<接頭辞なし絶対パス> の指定形式と、起票後の Events での確認手順、誤起票時の【無効・着手禁止】コメント付き再起票手順を明記済み — 次回 run で発火確認が残る
- blocked の理由の区別: デスクトップアプリの Kanban タブは blocked カードに block 種別（needs_input / dependency / transient / capability）のバッジを出す。Web ダッシュボード（`dashboard --isolated`）は種別を表示せず、CLI の `list` も ⊘ のみなので、CLI で確認するなら `hermes kanban show <id>` の Events の `'kind'` を見る
