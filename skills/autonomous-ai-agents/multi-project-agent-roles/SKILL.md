---
name: multi-project-agent-roles
description: "Use when Hermesの役割を複数プロジェクトで使い回す設計やプロジェクト登録を行うとき。"
version: 1.0.0
author: Hermes Agent
category: autonomous-ai-agents
---

# 複数プロジェクトでの役割共用とディレクトリ契約

## 標準ディレクトリ構成（2026-10-15 ユーザー裁定・vault 系プロジェクト共通）

プロジェクトルート配下の標準ディレクトリと意味。プロジェクト間で言い換えない（project_lead_* SOUL にもこの文言をそのまま書く）:
- `ideas/` — ユーザーが思いついたことをメモに書くためのディレクトリ
- `notes/` — PBI など、ある程度やることの塊になったものを保存しておくディレクトリ
- `outcomes/` — AI が作業結果を配置するディレクトリ。格納先が本文の指示や編集対象の続きから決まらない・判断に迷う場合はここに格納する
- `resources/` — 情報源を格納するディレクトリ
- `minutes/`（議事録）／`public_relations/`（広報資料）／`schedule/`（スケジュール）は必要なプロジェクトにのみ配備する（無いプロジェクトで勝手に作らない）

コード・モノレポ系（例: g01_${ORG_NAME}）はこの標準の対象外で、リポジトリ契約が優先。契約（.hermes.md）と実ディレクトリが食い違うときは実測（ls）を優先し、食い違いを kanban_comment に記録して人間が契約を更新する（p02 の resource/resources 実測の前例）。

2026-10-15、h01 / p01 / p02 / h02 の4プロジェクトの .hermes.md ディレクトリ契約節はこの標準に一括更新済み（機密条項・markdown規約・環境上の注意・起票テンプレート等の他節は保持。p01 の git/GitLab 節も保持）。権限は全標準ディレクトリ 編集可＋「上記以外は読み取りのみ」の共通ベースラインに統一した

## When to Use

- 役割（writer 等）を複数プロジェクトで共用するかプロジェクトごとに複製するか設計するとき
- 新しいプロジェクトルートを Hermes（デスクトッププロジェクト）に登録するとき
- 「このプロジェクトはどのディレクトリを参照/編集してよいか」の契約をどこに置くか決めるとき

## 役割共用 vs 複製の裁定

- 原則**共用**（writer は1つ）。プロジェクト差分は役割の外側（プロジェクト側の `.hermes.md` / 起票本文）に置く
- **複製するトリガーは3つだけ**: ①プロジェクトで別モデル/設定が必要 ②専用の認証情報が必要（ワーカーはプロファイルの .env しか読まないので、これが唯一の実質的理由になり得る） ③SOUL の要件がプロジェクト間で実際に矛盾する
- 複製すると学習が断片化する（memory/skill はプロファイル固有、`--clone-from` は実体コピー）。複製したら共通化すべき SOUL 部分を汎用 skill / criteria に切り出してから配布し、発散を防ぐ

## 契約の三層構造（置き場所）

- **プロジェクト側: プロジェクトルートの `.hermes.md`** — 参照可/編集可ディレクトリ・成果物名規則。Hermes が cwd から git root まで親を辿って1つだけ自動注入する（first match）。ドットファイルなので Obsidian のインデックス外になり、vault 検索を汚さない
- **タスク側: kanban 起票本文の【制約】節** — タスク単位の付与（「成果物は `<ルート>/outcomes/` 配下のみ、他は読み取りのみ」）。workspace は**絶対パスのみ**（`dir:` 接頭辞付きで渡すと spawn_failed×2 → gave_up で恒久詰み）
- **役割側: 共用プロファイルの SOUL.md は普遍条項のみ** — プロジェクト名・パスを一切書かない。「現プロジェクトの .hermes.md とカード本文が契約。宣言外は読み取りも禁止。曖昧なら自己判断せず needs_input」。これで共用役割をプロジェクト横断で使い回しても SOUL を編集しなくて済む

### Pitfalls

- 機密プロジェクトの `.hermes.md` には必ず「本プロジェクト固有の内容を memory / skill_manage に保存しない」を入れる — 共用役割の memory は毎セッション注入され、他プロジェクトのセッションに漏れる
- 契約は文脈による**指示であって強制ではない**。強制に寄せたいときは spawn 時の workspace を編集対象ディレクトリに閉じる（物理境界）＋危険操作の approval ゲートで組み合わせる
- 中央の一覧表（例: `~/${KANBAN_RUNS_DIR}/permissions.md`）は人間の索引に留める。ワーカーが読む正本にはしない — 共用役割が「自分は今どのプロジェクトか」を判断して一覧を引く経路は事故る（起票 workspace ミスと同型の詰みパターン）

## プロジェクト新規作成の手順

1. **実在構造を確認**: `ls -la` で既存資産を列挙する。既存の Obsidian ディレクトリに Hermes プロジェクトを後付けする場合が多く、`.hermes.md` には**実在するディレクトリ名**を書く（`outcome/` と決め打ちしない。実際は `outcomes/` 等バリエーションがある）
2. `.hermes.md` を作成: ディレクトリ契約＋機密条項（該当時）＋markdown 規約。markdown 規約には必ず「タイトル（H1・ファイル名）に Obsidian 禁止文字 `< > : " / \ | ? *` を使わない」を入れる（ユーザーの標準規約）
3. デスクトッププロジェクト登録: `tool_search` → `tool_describe` → `tool_call` で `desktop_project {action: create, name, path}`（path にアンカーするとチャットのワークスペースが移動する）
4. 検証: 返り値の id / slug / primary_path を読み返し、パスが一致することを確認する

kanban で使うときは起票本文の workspace にプロジェクトルートの絶対パスを渡す。ワーカーの cwd がその配下に来るので `.hermes.md` が自動注入され、共用役割の SOUL を触らずに済む

## Obsidian vault（WSL /mnt/c）をプロジェクトルートにする

- **可**。まず `mount | grep -i drvfs` でマウント確認。`metadata` 付きなら chmod も実用レベル
- 9p 特有の落とし穴:
  - 小ファイル大量アクセスが ext4 の数倍遅い（git clone / npm install / pytest）→ writer・doc 系は実害なし。build/test が重いタスクは workspace だけ ext4 に逃がし成果物のみ vault に書く混合構成が推奨
  - **inotify が発火しない** → `hermes kanban watch` や file-watch 系トリガーの監視対象に vault 直を使わない（監視は ext4 側で受け、書き込みは vault へ片方向）
  - **ケース非感覚**（C: ドライブ）→ 大文字小文字違いの同名ファイル禁止。成果物名の原文引き継ぎルールと合わせて曖昧名を禁止するだけで耐える
  - **CRLF 混入** → git 管理するなら `.gitattributes` で `* text=auto eol=lf`
- ユーザーの vault は Dropbox + remotely-save 経由。**`.hermes.md` はドットファイルなので sync 対象から外れる設定がある** — ローカルの Hermes 実行には影響なし。他デバイスでも見せる必要が出たら通常ノートにミラーして `.hermes.md` から参照指示する
- パスに日本語・スペースが入る（例: `アプリ`）ので、起票本文や create_task.sh に渡すときはクォートを明示する
- **9p での mv (tmp→rename) が一時的に Permission denied になる**（Dropbox 同期ロック）。patch/write_file が `mv: cannot move .hermes-tmp.*` で失敗したら即リトライか terminal での mv に切る。失敗時に `.hermes-tmp.*` の残骸が残る（内容は完成版）ので、掃除と内容検証を忘れない
