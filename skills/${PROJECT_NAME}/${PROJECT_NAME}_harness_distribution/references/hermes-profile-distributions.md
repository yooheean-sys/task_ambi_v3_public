# hermes profile 配布・エクスポート機構の要点

## 2つの共有経路
| | Distribution（git リポジトリ） | Export（tar.gz） |
|---|---|---|
| 導入 | `hermes profile install <repo>` | `hermes profile import` / チャットの /import |
| 更新 | `hermes profile update`（ユーザーデータ保持） | 再送 |
| 搭載物 | SOUL・config・skills・cron・mcp.json・plugins | 同左＋デスクトップのテーマ・レイアウト |
| 向き先 | 複数機器展開・公開・バージョン管理 | 1回限りの移行・その場共有 |

## distribution.yaml
- 必須は name のみ。任意: version・description・hermes_requires・author・license・env_requires（name/description/required/default）。
- env_requires は install 時に shell 環境と既存 .env に対してチェックされ、✓ set / needs setting を表示する。
- distribution_owned で配布対象リストを上書きできる（既定: SOUL.md・config.yaml・mcp.json・skills/・cron/・distribution.yaml）。
- update 時の config.yaml は既定で保持 — --force-config でリセット。
- .env.EXAMPLE は install 側が生成する（作者領域ではない）— 必要変数は env_requires で宣言し、自分で EXAMPLE ファイルを書かない。

## install の動作
- 一時クローン → manifest 表示 → env チェック → 確認（-y で省略可）→ プロファイル配置（.git/ は剥がす）。
- 予約名 hermes・test・tmp・root・sudo は拒否。
- cron は自動スケジュールされない。`hermes -p <name> cron list` で確認し明示有効化する。
- 配布は未署名 — 信頼対象は git ホストと作者。

## ハード除外（install/update 時に installer が強制除去・設定変更不可）
auth.json・.env・.env.EXAMPLE・memories/・sessions/・state.db と -shm/-wal・hermes_state.db・response_store.db とその -shm/-wal・logs/・workspace/・plans/・home/・*_cache/・local/・gateway.pid・gateway_state.json・processes.json・auth.lock・active_profile・.update_check
- これは受領者側の保護のみで、作者の git add は止めない。作者は git init の前に .gitignore（上記＋独自除外）を書く。

## export/import
- `hermes profile export <name> -o <path>` / `hermes profile import <file>`。チャット内では /export・/import。
- export ファイルは memories・sessions も含む — 公開には使わず、渡す前に中身を確認する。
- 付帯: `hermes profile info`（manifest 表示）・`hermes skills snapshot`（スキル構成の退避）・`hermes sync`（スキルだけの複数機器同期）。
