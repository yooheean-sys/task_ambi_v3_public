---
name: taskambi_boot
description: task_ambi V3（4階層カンバン組織）を起動して作業させるときの起動手順。
version: 0.3.0
author: ${USER_NAME_LOWER}, Hermes Agent
license: private
metadata:
  hermes:
    tags: [task_ambi, kanban, boot, 4tier-org]
    related_skills: [taskambi_kanban-agent-org, taskambi_project]
---

# taskambi_boot — 4階層カンバン組織の起動

通常の会話モードとは別に、task_ambi V3 設計の4階層カンバン組織（planner → project_lead → 第3層3役 → 実行15役）を kanban 上へ起動して作業させるとき専用の起動手順。発動中は成果物を自分で書かず、組織への起票・監視・検収サポート・完了報告を担う起動オーケストレーターとして振る舞う。

kanban のメカニクス（create / link / watch / archive・依存の向き・復旧手順）と起票本文テンプレートの正本は skill 'taskambi_kanban-agent-org' と `~/kanban-guide.md`。**起票前に 'taskambi_kanban-agent-org' を読み込んでから**以下の手順に入る。本ファイルはその内容を繰り返さない。

## When to Use

- 「taskambi起動して」「ta起動」「4階層カンバン組織で〜して」等、組織を起動して作業させる指示
- 対象リポジトリが決まっていて GitLab の PBI を指定して実行したいとき（glab で拾う）
- 使わない: 単発の質問・軽微な調整・組織を起動するまでもない作業 → 普通の会話で処理する

## 手順

### 1. 事前確認（起票前）

- [ ] `hermes profile list` — 全ペルソナの Gateway が running か。落ちていれば人間に報告して待つ
- [ ] `hermes kanban list` — 前回の残カードが無いか。あれば起票前に人間へ確認（archive するか続行するかの裁定）
- [ ] PBI を拾う場合のみ `glab auth status` — `Invalid token provided` 警告は出ても issue list が成功すれば続行してよい（実測: list・create・view・comment・close 全成功）。issue 操作自体が失敗したら人間に報告して待つ。詳細は手順 3.A.8

### 2. 組織モード判定 — ルートカードの assignee を決める

判定材料の優先順位: 人間の明示指示 > 対象リポジトリの origin URL > cwd パス。

1. プロジェクトを特定する:
   - cwd が `20_projects/20_<正式名>` 配下 → `<正式名>` を抽出する（例: `20_${PROJECT_P01_NAME}` → ${PROJECT_P01_NAME}）
   - 対象リポジトリがある → `git -C <repo> remote get-url origin` の GitLab グループで紐づける。実績マッピング: ${REPO_NAME}（`~/project/task_ambi/${REPO_NAME}`、origin `${GITLAB_URL_ORG}/${REPO_NAME}.0.git`）→ g01_${ORG_NAME}
   - 対象が `~/.hermes` や `~/${KANBAN_RUNS_DIR}` 配下（組織自体の SOUL・criteria 改訂系）→ プロジェクトに紐づかない扱いにする。この系の改訂適用は人間承認条項（harness 等の SOUL）に従う
   - 曖昧なら選択肢+推奨を付けて人間に尋ねる
2. `hermes profile list`（または `hermes kanban assignees`）で専任 `project_lead_<正式名>` が実在するか確認する。**profile 名は小文字化される**（実在例: `project_lead_${PROJECT_P01_NAME}`）が、assignee に指定する名前はデスクトッププロジェクト正式名のまま（`project_lead_${PROJECT_P01_NAME}`）でよい
3. 実在する → **プロジェクトモード**: ルート assignee = `project_lead_<正式名>`。planner を飛ばし、project_lead から下の3階層（project_lead → 第3層3役 → 実行15役）で運用する。planner の判定・振り分け機能が働かないため、ルート本文に対象プロジェクト・workspace・参照先（プロジェクトの .hermes.md とディレクトリ）を必ず明記する。契約上の位置関係に留意点がある場合（例: 対象リポジトリが SOUL 契約ルートの外）は、本文に人間の裁定（判断内容・承認日付）を1文明記する — 上位層はそれを根拠に着手し、疑義が残る点だけ needs_input に回す（実測: 第二拠点 ${REPO_NAME} では needs_input 不発火で着手・本文明記が根拠となった）
4. 実在しない / プロジェクト不特定 → **フル4階層モード**: ルート assignee = planner（専任の無いプロジェクトへのフォールバック配線は planner SOUL が担う）

### 3. 親タスクを確定する

**A. 対象リポジトリが決まっていて PBI の指定がある場合 — glab で拾う**

1. `cd <repo> && glab issue list` で開いた issue を出す（指定があれば `--label <label>` / `--assignee @me` で絞る）
2. 指定の PBI を全文読む: `glab issue view <iid> --comments`
3. issue のタイトル・本文・コメントを親タスク本文の材料にする。本文には issue の URL と iid を明記する。受け入れ条件を自分で膨らませない — issue に無い要件は対話に回すか【未確定点】に載せる
4. 候補が複数ヒットしたら選択肢+推奨を付けて人間に選ばせる
5. 指定された PBI がまだ存在しない場合は起票から始める（skill 'pbi' の grilling → 整形 → glab 起票の流れ）
6. GitLab への書き戻し（kanban ID を issue コメントする等）は既定では行わない。人間が指示したときだけ承認を得てから `glab issue comment`。ただし PBI 自身が成果物として issue コメント投稿を求めている場合はその投稿が PBI の契約であり、本文で許可範囲を明記して許す
7. PBI の成果物がファイルでない場合（issue コメント投稿等）は、親タスク本文に「成果物ファイル名は存在しない（成果物は ○○である）」と明記し、受け入れ条件に GitLab 側での実体確認（glab issue view でコメントが見える）を入れる。workspace へのファイル書き込みの要否も明記する
8. `glab auth status` に `Invalid token provided` 警告が出ても issue list / view が成功する場合は続行してよい（実測: list・create・view・comment・close は全て成功）。create / view が失敗したら人間に報告して待つ

**B. そうでない場合 — 対話で確定する**

1. 対話で確定する: 目的 / 対象（プロジェクト・リポジトリ・ディレクトリ）/ 成果物（ファイル名は原文）/ 受け入れ条件 / 制約 / 期限
2. 曖昧点は選択肢と推奨をセットで質問する（推奨を先頭に）
3. 対話の中で対象プロジェクトが確定したら手順 2 に戻り、組織モードを確定させてから続行

### 4. workspace を確定する

- プロジェクトモード: そのプロジェクトの実在ディレクトリ（コード系は ext4 側リポジトリ、vault 系は vault 配下の対象ディレクトリ）。2拠点プロジェクト（p01 の vault＋ext4 リポジトリ等）は主作業拠点を1つ指定し、もう一方は本文の参照先として書く
- フル4階層モードで対象不特定: `~/${KANBAN_RUNS_DIR}/<run名>/` を作り `pj_input/`（入力）と `outcome/`（成果物）に分ける
- 指定形式の区別（混同すると spawn_failed×2 → gave_up で恒久詰み）:
  - CLI `hermes kanban create` の `--workspace` は **`dir:<絶対パス>`（接頭辞付き）**
  - ワーカーが使うツール kanban_create は **workspace_kind='dir' + workspace_path=<接頭辞なしの絶対パス>**
  - 起票本文に workspace を書くときは「接頭辞なし絶対パス」と書く（本文がそのままツール引数にコピーされるため）

### 5. ルートカードを起票する

- 本文チェックリスト（テンプレート形は taskambi_kanban-agent-org「サンプル実行の手順」3）: 固定の成果物ファイル名（原文引き継ぎ・言い換え禁止）／workspace 統一の指示／「上位3層は分解・判断・検収のみ」の一文／【未確定点の扱い】3行型（未確定が無い場合もその旨明記）／プロジェクトモード時は対象プロジェクトと契約（.hermes.md）の参照指示
- 本文はファイル化して渡す（長い --body は承認ゲートで止まりやすい）:

```bash
hermes kanban create "<タイトル>" \
  --body-file body.md \
  --assignee <planner または project_lead_<正式名>> \
  --workspace dir:<絶対パス> \
  --max-runtime <規模に応じて。例: 40m> \
  --created-by taskambi_boot
```

- PBI・対話で確定済みの内容はそのまま起票してよい（追加の承認ゲートを挟まない）。確定していない点が残る場合、または起票のために新規ディレクトリを作る必要がある場合だけ、起票前に選択肢+推奨を付けて承認を得る
- 起票したルートカード ID を控える（完了時レポートの起点）

### 6. 監視する

- `hermes kanban watch` を background で流し、2〜4分ごとに `hermes kanban list` を確認する
- 監視中に増えたカード ID を随時記録する（完了時のレポートで拾い直さなくてよいように）
- 停滞の兆候: spawn_failed / gave_up / 同名カードの重複 / blocked。復旧は taskambi_kanban-agent-org の落とし穴節の手順に従う
- **分解役カードが完了した直後に「申告子タスク vs 実際に増えたカード」を突合し、逸脱は即座に封じ込める**（実測 2026-10-17: 5 run 中 3 run で分解役が同一内容を連投。親リンク無しの ready カード・scratch 誤起票・"ws-path probe" "test" 等のプローブ風タイトルが兆候）。突合で迷子を見つけたら正規カード（親リンク済み・本文に注記があるもの）だけを残し、其余に【無効・着手禁止】コメントを付けて `hermes kanban block <id> --ids <残り> --kind needs_input "重複起票のため無効化（正規カード <id> に集約）"` で止める。読み取り専用の重複は実害が無いが spawn 費用と混乱を避けるため blocked にする。封じ込めの経緯は親カードにも kanban_comment で記録する
- review の changes_requested → 自動 requeue → 再 spawn → 指摘のみ修正 → 再 review は**正常な自己修復**であり停滞ではない（実測: 2回自動発火・いずれも round 2 合格）。停滞と区別して放置する
- 分解役完了直後には、後続カードの依存親が「前提を実際に届けるカード（実装リーフ等）」になっているかも確認する。分解リードカードだけを依存親にすると premature promote になり、実行役が実測確認で自己停止して回収に余分な時間がかかる（実測: テスト1で発火・自己停止と再開で回収）。ルート本文に「順序依存は実装リーフを親にする」指示を入れておくと発火率が下がる
- needs_input が起きたら reason を要約して人間に伝える。回答は `hermes kanban comment <id> "<裁定>"` + `hermes kanban unblock <id>` の2段（dependency 待ち以外は自動再開しない）
- watch の停止は `ps aux | grep "kanban [w]atch"` で PID を確認してから kill（`pkill -f` は自分のシェルを巻き込む）

### 7. 完了判定と検収サポート

- [ ] `hermes kanban list` で全カード done を確認（list の2列目が ID・3列目が状態。`$3=="done" && $2 ~ /^t_/`）
- [ ] 人間検収の材料を提示する: 成果物の実体（パスとファイル存在）、人が自分で再実行して検算できるコマンド。ワーカーの summary / artifacts 申告を根拠にしない
- 検算用プローブ（独立再計算スクリプト等）を作ったら workspace 内に残す（実績: _verify_recompute.py）。/tmp に作ると後で突合できなくなる

### 8. 実行順序レポート（完了時に必ず出す）

どの役割（階層込み）がどういう順番で起票・実行したかを、マークダウン表で人間に報告する:

1. **archive 前に**本 run の全カード ID を確定する（監視中に記録した ID + `hermes kanban list` で漏れチェック）
2. 各カードを `hermes kanban show <id>` して title / assignee / 親カード / created / started / completed を収集する。**実行役の特定は `hermes kanban runs <id>` を使う** — list の assignee 列は最終 run のプロファイル（多くは reviewer＝親役）を表示するため。起票者 = そのカードを親として起票した役（親カードの assignee）。ルートカードと人間が直接起票した補助カードの起票者は「起動セッション／人間」（show の Events の created_by で裏取りできる）
3. 表の列: 順序 | created | カード（タイトル） | 起票者（役+階層） | 担当役（assignee+階層） | completed | 直列/並行
4. 依存グラフの分岐点 — どこが並行になり、どこが直列チェーンだったか — を1〜2文で添える
5. 完了していないカード（blocked / triage 落ち等）が残っていれば、その状態と扱いもレポートに含める
6. レポート提示後、人間の承認を得てから後片付け: `hermes kanban list | awk '$2 ~ /^t_/ {print $2}' > ids.txt` で ID を採集し、`hermes kanban archive $(cat ids.txt)`（単独の短いコマンドで。承認がタイムアウトしたら勝手に再実行せず状況と次の一手を提示して待つ）

## Pitfalls

- CLI の `--workspace` は `dir:` 接頭辞付き、ワーカー用ツールの workspace_path は接頭辞なし — 混同すると spawn_failed×2 → gave_up で恒久詰み
- profile ディレクトリ名は小文字化されるが、assignee はデスクトッププロジェクト正式名で指定する
- プロジェクトモード（planner 飛ばし）では判定・振り分けがルート本文の明記頼みになる — 参照先（.hermes.md・ディレクトリ）を省略しない
- 分解役ワーカーの kanban_create 連投（重複・プローブ起票）が低コストモデルで再発しやすい（実測: 5 run 中 3 run・planner 配下の project_lead と system_engineer で発生）。対策は二段構えで適用済み: 分解担当5役 SOUL の「起票の自己検証」条項（2026-10-17 人間承認・次回 spawn から反映）＋本スキル手順6の突合→即封じ込め。発火確認は次回 run
- 長い外部書き込みコマンド（glab issue create 等）や heredoc→python へのパイプは承認ゲートで止まりやすい（実測: ゲートタイムアウト2回）。タイムアウトしたら再実行せず状況と次の一手を人間に提示して待つ。人間の返信で承認が得られた後は同じコマンドを再実行してよい
- その他の kanban メカニクス上の罠（重複起票・詰みカード復旧・差戻しループ等）は skill 'taskambi_kanban-agent-org' の落とし穴節が正本

## Verification

- 起票直後: `hermes kanban list` でルートカードが見え、Events に dependency_wait や spawn_failed が無い
- 完了時: レポートに載せた全カードが本 run の親子リンクで連結している（`hermes kanban show` の親子確認）。archive 実行後は `hermes kanban list` から消えている
