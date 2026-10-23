---
name: vault_inbox_classification
description: ${VAULT_NAME} vault の 00_inbox を各ディレクトリへ自動分類・格納するときに使用。
version: 1.0.0
author: ${USER_NAME_LOWER}
license: MIT
metadata:
  hermes:
    tags: [obsidian, vault, inbox]
    related_skills: []
---

# vault_inbox_classification — 00_inbox 自動分類

対象 vault（固定。別 vault では使わない）:

```
${VAULT_ROOT}
```

格納の記録は 1 実行につき 1 ファイルとして `00_inbox/logs/分類ログ_YYYY-MM-DD_HHMM.md` に新規作成して残す。「どこに何を置いたか」は logs 配下の新しい分類ログを見れば追跡できる。削除は一切しない（迷ったら `91_extra/temp` へ退避）。

## When to Use

- 「00_inbox を整理して」「inbox を分類して」「メモを各フォルダに振り分けて」等を頼まれたとき
- inbox 分類の定期実行（cron から呼ばれる想定。その場合は承認なしで適用してよい）。cron の実行には 1回あたり約 3分の上限があるため、スキャン・本文読み・map作成・dry-run・apply のツール呼び出しはできるだけ圧縮すること
- vault が ${VAULT_NAME} 以外のときはこの skill を使わない

## 触ってよいもの / いけないもの

- 対象: `00_inbox` 直下のファイルのみ。`00_inbox/logs` は分類ログの置き場であり分類対象外（「要確認」にも入れず無視する）。それ以外のサブディレクトリがあったらログに「要確認」と記して触らない
- 触らない: `00_inbox/logs` 配下のファイル（分類ログも含めどこへも移動しない）、分類ログそのもの（旧 `00_分類ログ.md`、`分類ログ_*.md`。inbox 直下に紛れていても移動しない）、vault ルート直下のファイル、`legacy/`、`templates/`、`scripts/`、`.obsidian/`
- 移動先に `00_inbox` 配下（`00_inbox/logs` を含む）は指定できない
- 移動は同梱スクリプトの mv のみ。削除・内容改変はしない。remotely-save 同期中でも mv は問題ない

## ディレクトリ地図（行き先候補）

| ディレクトリ | 用途・目安 |
|---|---|
| `10_journal/10_01_daily` ほか | 日誌。inbox には基本来ない |
| `20_projects/20_${PROJECT_P01_NAME}` `20_${PROJECT_P02_NAME}` `20_p03_nuclear` `20_g01_${ORG_NAME}` `20_${PROJECT_H01_NAME}` `20_${PROJECT_H02_NAME}` `20_h03_physical_AI` | 特定プロジェクト宛のメモ。サブ: `ideas`(アイデア・検討) / `notes`(作業メモ・既定) / `minutes`(議事録) / `outcomes`(成果物) / `resources`(資料) |
| `20_projects/20_xxx_others` | プロジェクト宛だが既存プロジェクトに該当なし。直下へ |
| `30_knowledges/ai` | AI 関連の知識・ノウハウ（サブ: `communicator`, `上司AI`） |
| `30_knowledges/human` | それ以外の知識・学習（サブ: `books`, `love`, `others`）。迷ったら `human/others` |
| `40_areas/career` `cowork` `enjoy` `entrepreneurship` `life` `relationships` `self` `self_blushup_communication` `self_blushup_visual` `self_finance` `self_narratives` | 継続的な生活領域。健康・医療は `life`（`病院` サブあり）、投資は `self_finance`、仕事術は `cowork` |
| `50_idea` | まだ形になっていないアイデア・思考断片 |
| `60_resources` | 外部資料・参照クリップ |
| `70_procedures/70_01_manual` | 手順書・マニュアル（サブ: `software_development`） |
| `70_procedures/70_02_memos/<topic>` | ツール別メモ。既存 topic: `ai_agent` `ai_setting` `ai_tools` `bash` `beads` `browser` `discord` `espanso` `git` `internal_network` `iphone` `langfuse` `local-llm` `mac` `my_taskmanagement` `OA機器` `obsidian` `office` `signoz` `software_development` `teams` `vscode` `windows`。無い topic は小文字英数字で新規 topic ディレクトリを作ってよい |
| `70_procedures/70_03_company` | 会社関連の手順・情報 |
| `80_reports/anzentaiwa` `80_reports/q` | レポート |
| `90_keep` | 継続リスト。既存は `90_01_`〜`90_09_` 命名 → 新規は `90_10_` から番号を続ける（`rename` を使用） |
| `90_keep/mobile` | モバイルからの capture（`YYYY-MM-DD.md`） |
| `91_extra/temp` | 一時・分類不能の退避先（fallback） |
| `91_extra/images` | 画像等の添付ファイル |
| `99_crypt_manegement` | アカウント・暗号資産管理 |

## 手順

1. **スキャン**: `00_inbox` 直下を一覧表示。0 件なら「inbox は空」と報告して終了。
2. **判定**: 各ファイルの中身を読む（長い場合は先頭 80 行で十分、必要なら末尾も）。ファイル名と本文から行き先を 1 つ決め、理由を 1 行書く。具体性が高い先を優先（明示プロジェクト > 30/40/70 の専門分類 > `50_idea` / `60_resources`）。
3. **マップ作成**: scratch（`$BH_AGENT_WORKSPACE`）に `map.json` を書く。形式は下記。
4. **dry-run**: スクリプトを `--apply` なしで実行し、dest 未存在・不正指定を潰す。
5. **承認**: 対話実行では移動計画の表をユーザーに見せ、承認を取ってから適用する（選択肢＋推奨をセットで提示）。cron 等の自動実行では承認なしで適用してよい。
6. **適用**: `--apply` で実行し、出力の移動数・退避・エラーを確認する。
7. **報告**: 「ファイル → 行き先（理由）」の一覧をユーザーへ提示する。同じ内容が `00_inbox/logs` の当日の分類ログにも記録されていることを伝える。

## 判定ルール

- 迷ったら進めないより退避: `91_extra/temp` に note「分類不能: 要確認」。対話実行なら判断が割れるときだけ、選択肢＋推奨つきで質問してよい。
- 競合コピー（`○○ 1.md` `○○ 2.md`）: 本体と同じ dest を指定してよい。移動先に同名ファイルがあり中身が同一なら、スクリプトが自動で `91_extra/temp` へ退避しログに注記する（削除はしない）。中身が違えば `YYYYMMDD` 接尾で改名して両方残す。
- 非 `.md`: 画像・写真 → `91_extra/images`、それ以外 → `91_extra/temp`。
- `90_keep` へ入れるときだけ `rename` で番号を振る（例: `90_10_字幕見ながら英語.md`）。それ以外はファイル名を変えない。
- 全件どこかへ格納する（inbox に残す判定はしない。残すと次回も対象になりループする）。

## スクリプト

skill 同梱の `scripts/classify_inbox.py`（stdlib のみ・python3）。skill_view の linked_files で実パスを確認してから実行する。

```bash
python3 <skill_dir>/scripts/classify_inbox.py --vault <vault> --map <map.json>           # dry-run
python3 <skill_dir>/scripts/classify_inbox.py --vault <vault> --map <map.json> --apply   # 実行
```

`map.json`:

```json
[
  {"file": "Windows と WSL のバックアップ.md", "dest": "70_procedures/70_02_memos/windows", "note": "バックアップ手順メモ"},
  {"file": "new.md", "dest": "91_extra/temp", "note": "分類不能: 要確認"}
]
```

- `file`: 00_inbox 直下のファイル名（必須） / `dest`: vault 相対ディレクトリ（必須・既存であること） / `note`: ログへ追記する 1 行（任意） / `rename`: 移動時の新ファイル名（任意）
- dest が未存在・保護ディレクトリ（legacy 等）・vault ルートの場合は WARN/SKIP になる。dry-run で潰してから apply する。
- 同名衝突は自動処理: 同一内容 → `91_extra/temp` 退避、別内容 → `YYYYMMDD` 接尾で改名。

## 分類ログの仕様

- 場所: `00_inbox/logs/分類ログ_YYYY-MM-DD_HHMM.md`。1 実行につき 1 ファイルを新規作成する（既存ログへの追記・整形はしない）。
- 形式:

```
# 分類ログ

## 2026-10-21 17:54（移動 12 / 退避 1）

- [[70_procedures/70_02_memos/windows/Windows と WSL のバックアップ|Windows と WSL のバックアップ]] — バックアップ手順メモ
```

- ユーザーは logs 配下の新しい分類ログを見れば、その実行で何がどこへ行ったか分かる。Obsidian の検索でも追跡できる。
- 移動 0 件の実行ではログファイルは作らない。
- 旧形式 `00_inbox/logs/00_分類ログ.md`（2026-10-21 までの累積記録）は過去記録としてそのまま残す。新規追記・整形・削除はしない。
- ログ内にプロファイルの `~/` 表記等を書かない（vault 相対パスのみ）。
