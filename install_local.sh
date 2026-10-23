#!/usr/bin/env bash
# ============================================================================
# install_local.sh — task_ambi_v3_public（task-ambi-harness）ローカル導入スクリプト
#
# 出典: task_ambi_v3/docs/harness_migration_plan.md §5 P4（install_local.sh 実装）
# 上位層裁定（親カード t_5b7e0e6c で確定した内容を継承・原文どおり）:
#  ① 実行形態は「hermes profile 機能による導入」を前提とする
#  ② ソースは task_ambi_v3_public リポジトリ内のファイルのみを対象とする
#  ③ 値の供給は .env（導入先が記入）の HARNESS_* 変数のみから読む。
#     名称マップ（HARNESS_PROJECT_NAME_MAP から ${PROJECT_*_NAME} 等を展開）も含め、
#     F4 の replace_for_deploy() と同一の結果になること。
#     実値のハードコード禁止・実値を画面に出さない
#  ④ 実行モードは --dry-run（必須実装・書き込まない）と --apply の2モード。
#     配置先は .env の HARNESS_HOME を尊重（HARNESS_HOME は必須キー。未設定・REPLACE_ME・空値のときは欠落キー一覧を表示して exit 1 する＝既定への暗黙フォールバックはしない）。
#     ※dry-run の出力のうち「配置先パス」は導入先が自分で .env に記入した値であり、
#      ドライランの目的（配置先確認）のために実パスのまま出力する。
#      置換後の語（値テーブル）はマスク表示（<MASKED:len=N>）とする。
#  ⑤ profile 作成は "hermes profile create --clone-from default <名前>" を呼ぶ
#  ⑥ 配布対象は配置先 ~/.hermes にのみ書く（git repo には書かない）
#  ⑦ 本リポジトリへの commit は可（push・remote 設定なし）
#
# 処理順序（§5 P4）:
#  ① hermes 導入確認（未導入なら install.sh 案内で終了）
#  ② .env 読み込み（無ければ .env.EXAMPLE をコピーして記入を案内して終了）
#  ③ 逆方向置換の準備（HARNESS_* → プレースホルダ値。欠落キーは一覧表示して失敗）
#  ④ ファイル配置（内容＋ディレクトリ名の両方を置換）
#  ⑤ 25役生成（hermes profile create --clone-from default ＋ souls/ から SOUL 差し替え）
#  ⑥ cron jobs.json 配置（既存は .orig 退避）＋ cron 有効化手順の表示
#  ⑦ 導入確認（profile list・配置ファイルの存在確認）
#
# 置換テーブル（③の正本）: F4 scripts/harness_replacements.py の REVERSE_MAP と
# 完全一致させる（24 プレースホルダ・23 環境変数キー。KANBAN_RUNS_ROOT と
# KANBAN_RUNS_DIR は同じ HARNESS_KANBAN_RUNS_DIR を共有する）。
# 埋め込み一覧方式（動的走査禁止）: 一覧に無い ${...} は置換しない。
#
# 使い方:
#   cd task_ambi_v3_public
#   cp .env.EXAMPLE .env   # REPLACE_ME を導入先の実値で置き換える
#   bash install_local.sh --dry-run              # 書き込まず配置先と置換内容を確認
#   bash install_local.sh --apply                # 実配置（profile 作成を含む）
#   bash install_local.sh --apply --skip-confirm # 確認プロンプトを省略（自動実行用）
#   bash install_local.sh --replace-test --env FILE < input.txt > output.txt
#       # 逆方向置換の単体テスト用（配置処理なし。stdin を置換して stdout へ）
#
# .env に必要なキー（.env.EXAMPLE に無いキーは導入先が追記する）:
#   HARNESS_HOME, HARNESS_USER_HOME, HARNESS_VAULT_ROOT, HARNESS_KANBAN_RUNS_DIR,
#   HARNESS_PROJECT_ROOT, HARNESS_DASHBOARD_BASIC_AUTH_USERNAME,
#   HARNESS_DASHBOARD_BASIC_AUTH_PASSWORD_HASH, HARNESS_DASHBOARD_BASIC_AUTH_SECRET,
#   HARNESS_USER_NAME, HARNESS_USER_NAME_LOWER, HARNESS_USER_HOME_MAC,
#   HARNESS_VAULT_NAME, HARNESS_LOCAL_IP, HARNESS_GITLAB_URL_ORG, HARNESS_GITLAB_HOST,
#   HARNESS_ORG_ROOT, HARNESS_ORG_NAME, HARNESS_REPO_NAME, HARNESS_PROJECT_NAME,
#   HARNESS_PROJECT_H01_NAME, HARNESS_PROJECT_P01_NAME, HARNESS_PROJECT_P02_NAME,
#   HARNESS_PROJECT_H02_NAME
#   （PROJECT_*_NAME / ORG_NAME / REPO_NAME は HARNESS_PROJECT_NAME_MAP の
#     「一般名=実名」ペア（例: g01=...,h01=...,p01=...,p02=...,h02=...,pj=...,org=...,repo=...）
#     からも供給できる。直値キーが優先される）
# ============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 埋め込み一覧（③の正本）: F4 REVERSE_MAP と完全一致・24 プレースホルダ。
# 形式: "プレースホルダ名:HARNESS_* キー"
# ---------------------------------------------------------------------------
PLACEHOLDER_MAP=(
  "VAULT_ROOT:HARNESS_VAULT_ROOT"
  "REPO_ROOT:HARNESS_PROJECT_ROOT"
  "ORG_ROOT:HARNESS_ORG_ROOT"
  "KANBAN_RUNS_ROOT:HARNESS_KANBAN_RUNS_DIR"
  "HERMES_HOME:HARNESS_HOME"
  "USER_HOME:HARNESS_USER_HOME"
  "USER_HOME_MAC:HARNESS_USER_HOME_MAC"
  "USER_NAME:HARNESS_USER_NAME"
  "USER_NAME_LOWER:HARNESS_USER_NAME_LOWER"
  "VAULT_NAME:HARNESS_VAULT_NAME"
  "LOCAL_IP:HARNESS_LOCAL_IP"
  "KANBAN_RUNS_DIR:HARNESS_KANBAN_RUNS_DIR"
  "GITLAB_URL_ORG:HARNESS_GITLAB_URL_ORG"
  "GITLAB_HOST:HARNESS_GITLAB_HOST"
  "ORG_NAME:HARNESS_ORG_NAME"
  "REPO_NAME:HARNESS_REPO_NAME"
  "PROJECT_NAME:HARNESS_PROJECT_NAME"
  "PROJECT_H01_NAME:HARNESS_PROJECT_H01_NAME"
  "PROJECT_P01_NAME:HARNESS_PROJECT_P01_NAME"
  "PROJECT_P02_NAME:HARNESS_PROJECT_P02_NAME"
  "PROJECT_H02_NAME:HARNESS_PROJECT_H02_NAME"
  "DASHBOARD_BASIC_AUTH_USERNAME:HARNESS_DASHBOARD_BASIC_AUTH_USERNAME"
  "DASHBOARD_BASIC_AUTH_PASSWORD_HASH:HARNESS_DASHBOARD_BASIC_AUTH_PASSWORD_HASH"
  "DASHBOARD_BASIC_AUTH_SECRET:HARNESS_DASHBOARD_BASIC_AUTH_SECRET"
)

# 未知プレースホルダ検出用の接頭辞（一覧外の ${...} を検出するための候補集合）。
# F4 の REVERSE_MAP に無いが、導入先環境で新しく追加されたプレースホルダの検出用。
PLACEHOLDER_PREFIXES=(
  HERMES_ USER_ VAULT_ KANBAN_ ORG_ REPO_ PROJECT_ DASHBOARD_ GITLAB_ LOCAL_
)

# HARNESS_PROJECT_NAME_MAP の一般名 → HARNESS_* キーの対応。
# criteria 一般化の復元用（例: g01=work_demo,h01=h01_dummy,p01=p01_dummy,...）。
NAME_MAP_KEYS=(
  "g01:HARNESS_ORG_NAME"
  "org:HARNESS_ORG_NAME"
  "pj:HARNESS_PROJECT_NAME"
  "project:HARNESS_PROJECT_NAME"
  "h01:HARNESS_PROJECT_H01_NAME"
  "p01:HARNESS_PROJECT_P01_NAME"
  "p02:HARNESS_PROJECT_P02_NAME"
  "h02:HARNESS_PROJECT_H02_NAME"
  "repo:HARNESS_REPO_NAME"
)

# テキストとして置換する拡張子（F4 の TEXT_SUFFIXES 相当）＋特殊ファイル名。
# これ以外（png 等・バイナリ）は置換せずそのまま配置する。
TEXT_SUFFIXES=(md txt yaml yml json toml py sh cfg ini xml html css js ts csv log conf example)
TEXT_SPECIAL_NAMES=(Dockerfile Makefile .gitignore .gitconfig)

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE=""
ENV_FILE=""
SKIP_CONFIRM="no"
DRY_RUN="no"

# ---------------------------------------------------------------------------
# グローバル状態
# ---------------------------------------------------------------------------
declare -A RESOLVED=()      # HARNESS_* キー → 値（.env から読む・表示しない）
declare -A PH_VALUES=()     # プレースホルダ名 → 値（置換用）
declare -A PH_SOURCE=()     # プレースホルダ名 → 供給源 (direct | name-map)
MISSING_KEYS=()             # 欠落 HARNESS_* キーの一覧
SED_ARGS=()                 # sed に渡す引数配列
DEST=""                     # 配置先（HARNESS_HOME）
KANBAN_RUNS_DEST=""         # criteria 配置先（HARNESS_KANBAN_RUNS_DIR）

# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
info() { printf '%s\n' "$*"; }

# 実値を画面に出さないためのマスク（長さのみ表示・裁定③）
mask_value() { printf '<MASKED:len=%s>' "${#1}"; }

# sed の置換文字列側をエスケープ（\ / &）
sed_escape() { printf '%s' "$1" | sed -e 's/[\\/&]/\\&/g'; }

# ---------------------------------------------------------------------------
# .env パース（KEY=VALUE 形式。コメント行 # と空行をスキップ・前後空白トリム）
# .env.EXAMPLE と同じ形式。値に = が含まれてもよい（最初の = で分割）
# ---------------------------------------------------------------------------
parse_env_file() {
  local file="$1" line trimmed key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    trimmed="${line#"${line%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    [[ -z "$trimmed" || "$trimmed" == \#* || "$trimmed" != *=* ]] && continue
    key="${trimmed%%=*}"
    val="${trimmed#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    val="${val#"${val%%[![:space:]]*}"}"
    val="${val%"${val##*[![:space:]]}"}"
    [[ -z "$key" ]] && continue
    printf '%s\t%s\n' "$key" "$val"
  done < "$file"
}

# HARNESS_PROJECT_NAME_MAP（一般名=実名 のカンマ区切りペア）を展開し、
# HARNESS_PROJECT_*_NAME / HARNESS_ORG_NAME / HARNESS_REPO_NAME に値を供給する。
# 直値キーが既にある場合は上書きしない（裁定③・F4 と同一の結果）。
expand_name_map() {
  local map_val="${RESOLVED[HARNESS_PROJECT_NAME_MAP]:-}"
  [[ -n "$map_val" && "$map_val" != REPLACE_ME ]] || return 0
  local IFS=',' pairs pair gen real spec key
  read -r -a pairs <<< "$map_val"
  for pair in "${pairs[@]}"; do
    pair="${pair//[[:space:]]/}"
    [[ "$pair" == *=* ]] || continue
    gen="${pair%%=*}"
    real="${pair#*=}"
    [[ -n "$gen" && -n "$real" && "$real" != REPLACE_ME ]] || continue
    for spec in "${NAME_MAP_KEYS[@]}"; do
      key="${spec#*:}"
      if [[ "${spec%%:*}" == "$gen" ]]; then
        if [[ -z "${RESOLVED[$key]:-}" ]]; then
          RESOLVED["$key"]="$real"
        fi
        break
      fi
    done
  done
}

# ---------------------------------------------------------------------------
# ③値の供給: .env の HARNESS_* 変数のみから読み、プレースホルダ値を構築する。
#   - REPLACE_ME（.env.EXAMPLE の未記入値）・空値は欠落扱い
#   - 欠落キーは MISSING_KEYS に集め、呼び出し側が一覧表示して失敗させる
#   - 名称マップ展開を含む（裁定③）
#   - 値の導出（basename 等）は行わない（③「のみから読む」を厳守）
# ---------------------------------------------------------------------------
build_env() {
  local key val entry ph
  while IFS=$'\t' read -r key val; do
    [[ "$key" == HARNESS_* ]] || continue
    RESOLVED["$key"]="$val"
  done < <(parse_env_file "$ENV_FILE")

  expand_name_map

  for entry in "${PLACEHOLDER_MAP[@]}"; do
    key="${entry#*:}"
    ph="${entry%%:*}"
    val="${RESOLVED[$key]:-}"
    if [[ -z "$val" || "$val" == REPLACE_ME ]]; then
      MISSING_KEYS+=("$key")
      continue
    fi
    PH_VALUES["$ph"]="$val"
    if [[ "$key" == HARNESS_PROJECT_NAME_MAP ]]; then
      PH_SOURCE["$ph"]="name-map"
    else
      PH_SOURCE["$ph"]="direct"
    fi
  done
}

# sed 引数配列の構築（欠落キーは式を作らない・プレースホルダ残存）
build_sed_args() {
  local ph val esc
  SED_ARGS=()
  for ph in "${!PH_VALUES[@]}"; do
    val="${PH_VALUES[$ph]}"
    esc="$(sed_escape "$val")"
    SED_ARGS+=(-e "s/[$][{]${ph}[}]/${esc}/g")
  done
  if [[ ${#SED_ARGS[@]} -eq 0 ]]; then
    die '置換式が 1 つも生成されませんでした（全キー欠落）'
  fi
}

replace_stream() { sed "${SED_ARGS[@]}"; }
replace_path()   { printf '%s' "$1" | replace_stream; }

# F4 相当のテキスト判定: 拡張子が TEXT_SUFFIXES または特殊ファイル名ならテキスト。
is_text_file() {
  local f="$1" name ext
  name="$(basename "$f")"
  for name_candidate in "${TEXT_SPECIAL_NAMES[@]}"; do
    [[ "$name" == "$name_candidate" ]] && return 0
  done
  ext="${name##*.}"
  [[ "$ext" == "$name" ]] && return 1   # 拡張子なし
  for ext_candidate in "${TEXT_SUFFIXES[@]}"; do
    [[ "${ext,,}" == "$ext_candidate" ]] && return 0
  done
  return 1
}

# 置換対象ファイルの列挙（.git・本スクリプト・.env・バイナリ拡張子を除外）。
find_target_files() {
  find "$SRC_ROOT" -type f \
    ! -path '*/.git/*' \
    ! -name 'install_local.sh' \
    ! -name '.env' \
    ! -name '.env.EXAMPLE' \
    ! -name '*.png' ! -name '*.jpg' ! -name '*.jpeg' ! -name '*.gif' \
    ! -name '*.ico' ! -name '*.pdf' ! -name '*.pyc' ! -name '*.so' \
    ! -name '*.db' ! -name '*.sqlite3' \
    -print0
}

# 未知プレースホルダの検出（③付随）: 埋め込み一覧に無い ${X} で X が
# PLACEHOLDER_PREFIXES のいずれかに一致するものを列挙する。
# 普通のシェル変数（${NC}・${HOME} 等・接頭辞不一致）は誤検知しない。
# 出力: 未知トークンの一覧（1行1個・重複除去）。空なら未知なし。
detect_unknown_placeholders() {
  local known pattern tok
  known="|$(IFS='|'; printf '%s|' "${PLACEHOLDER_MAP[@]%%:*}")"
  pattern="[$][{]($(IFS='|'; printf '%s' "${PLACEHOLDER_PREFIXES[*]}"))[A-Z0-9_]+[}]"
  while IFS= read -r tok; do
    [[ -z "$tok" ]] && continue
    tok="${tok:2}"      # "${" を除去
    tok="${tok%?}"      # 末尾 "}" を除去
    [[ "$known" == *"|$tok|"* ]] && continue
    printf '%s\n' "$tok"
  done < <(grep -rhoE --exclude-dir=.git "$pattern" \
      --include='*.md' --include='*.txt' --include='*.yaml' --include='*.yml' \
      --include='*.json' --include='*.py' --include='*.sh' --include='*.toml' \
      --include='*.cfg' --include='*.ini' --include='*.example' \
      "$SRC_ROOT" 2>/dev/null | sort -u)
}

# ---------------------------------------------------------------------------
# 1ファイルの配置（内容置換を適用して dest へ）。
# テキストファイル（F4 相当判定）は sed 置換・それ以外はそのままコピー。
# ---------------------------------------------------------------------------
install_one_file() {
  local src="$1" dest="$2"
  if [[ ! -f "$src" ]]; then
    warn "配置元ファイルが無い（スキップ）: $src"
    return 0
  fi
  if [[ "$DRY_RUN" == "yes" ]]; then
    printf '[dry-run] cp %s -> %s\n' "${src#"$SRC_ROOT/"}" "$dest"
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  if is_text_file "$src"; then
    replace_stream < "$src" > "$dest"
  else
    cp -p "$src" "$dest"
  fi
}

# ディレクトリ配下を一括配置。strip は dest 側で剥がす相対接頭辞（例: criteria/）。
install_tree() {
  local src_dir="$1" dest_base="$2" strip="${3:-}" f rel dest
  if [[ ! -d "$src_dir" ]]; then
    warn "配置元ディレクトリが無い（スキップ）: $src_dir"
    return 0
  fi
  while IFS= read -r -d '' f; do
    rel="${f#"$src_dir"}"
    rel="${rel#/}"
    if [[ -n "$strip" && "$rel" == "$strip"* ]]; then
      rel="${rel#"$strip"}"
    fi
    dest="${dest_base%/}/${rel}"
    # 相対パス内のプレースホルダ（ディレクトリ名・ファイル名）も置換する（裁定②）
    dest="$(replace_path "$dest")"
    install_one_file "$f" "$dest"
  done < <(find "$src_dir" -type f -print0 | sort -z)
}

# ---------------------------------------------------------------------------
# ①hermes 導入確認
# ---------------------------------------------------------------------------
step1_hermes_check() {
  info '=== step1: hermes 導入確認 ==='
  if command -v hermes >/dev/null 2>&1; then
    info "hermes: $(command -v hermes)"
    return 0
  fi
  cat >&2 <<'EOF'
ERROR: hermes コマンドが見つかりません。
       task-ambi-harness の導入には hermes が必要です。
       公式の install.sh で導入してから再実行してください:
         https://github.com/nousresearch/hermes-agent  (install 手順を参照)
EOF
  exit 1
}

# ---------------------------------------------------------------------------
# ②.env 読み込み（無ければ .env.EXAMPLE をコピーして記入を案内して終了）
# ---------------------------------------------------------------------------
step2_load_env() {
  info '=== step2: .env の読み込み ==='
  if [[ -z "$ENV_FILE" ]]; then
    ENV_FILE="$SRC_ROOT/.env"
  fi
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ ! -f "$SRC_ROOT/.env.EXAMPLE" ]]; then
      die '.env も .env.EXAMPLE も見つかりません: '"$SRC_ROOT"
    fi
    if [[ "$DRY_RUN" == "yes" ]]; then
      info '[dry-run] .env が無いため配置プレビューはできません。'
      info '[dry-run] 以下を実行して .env を作成し、REPLACE_ME を導入先の実値で記入してください:'
      info "[dry-run]   cp $SRC_ROOT/.env.EXAMPLE $ENV_FILE"
      die 'dry-run 中止: .env が未作成です（.env.EXAMPLE をコピーして記入後、再実行）'
    fi
    cp "$SRC_ROOT/.env.EXAMPLE" "$ENV_FILE"
    info ".env.EXAMPLE を $ENV_FILE にコピーしました。"
    cat >&2 <<'EOF'
ERROR: .env を作成しましたが、まだ REPLACE_ME のままです。
       .env を編集して HARNESS_* 変数に導入先の実値を記入してから、
       再度 install_local.sh を実行してください。
EOF
    exit 1
  fi
  info "env: $ENV_FILE（値は表示しません）"
}

# ---------------------------------------------------------------------------
# ③逆方向置換の準備（env 構築＋欠落チェック＋sed 式構築＋未知トークン検出）
# ---------------------------------------------------------------------------
step3_prepare_replacement() {
  info '=== step3: 逆方向置換の準備 ==='
  build_env
  if [[ ${#MISSING_KEYS[@]} -gt 0 ]]; then
    warn '次の HARNESS_* キーが .env に無いか REPLACE_ME のままです:'
    local key
    for key in "${MISSING_KEYS[@]}"; do
      warn "  - $key"
    done
    cat >&2 <<'EOF'
ERROR: HARNESS_* 変数が不足しています。上記のキーを .env に追記して
       導入先の実値を記入してから、再度実行してください。
       （PROJECT_*_NAME / ORG_NAME / REPO_NAME は HARNESS_PROJECT_NAME_MAP の
         一般名=実名 ペアからも供給できます）
EOF
    exit 1
  fi
  build_sed_args

  # 未知プレースホルダ検出（③付随: 一覧外のハーネス接頭辞トークンは失敗）
  local unknowns
  unknowns="$(detect_unknown_placeholders)"
  if [[ -n "$unknowns" ]]; then
    warn '置換テーブルに無い未知のプレースホルダが検出されました:'
    local tok
    while IFS= read -r tok; do
      warn "  - \${$tok}"
    done <<< "$unknowns"
    die '未知プレースホルダを解決するまで導入を中止します（.env または本スクリプトの置換テーブルを確認）'
  fi
  info "置換準備完了: ${#SED_ARGS[@]} 式（${#PH_VALUES[@]} プレースホルダ）"
}

# 置換テーブルの表示（値はマスク・dry-run の確認用）
show_replacement_table() {
  local ph key
  info '置換テーブル（値はマスク表示）:'
  for ph in "${!PH_VALUES[@]}"; do
    for entry_pair in "${PLACEHOLDER_MAP[@]}"; do
      if [[ "${entry_pair%%:*}" == "$ph" ]]; then
        key="${entry_pair#*:}"
        break
      fi
    done
    printf '  ${%s} <- %s [%s] (%s)\n' "$ph" "$(mask_value "${PH_VALUES[$ph]}")" "${PH_SOURCE[$ph]:-direct}" "$key"
  done
}

# ---------------------------------------------------------------------------
# ④ファイル配置（skills・SOUL.md・config.yaml・mcp.json・agent-hooks・criteria）
# ---------------------------------------------------------------------------
step4_install_files() {
  info "=== step4: ファイル配置 ==="
  info "配置先: $DEST（HARNESS_HOME）"
  if [[ "$DRY_RUN" == "yes" ]]; then
    info '[dry-run] 書き込みは行いません（配置先パスと置換後の語を表示するのみ）'
  fi
  install_tree "$SRC_ROOT/skills" "$DEST/skills"
  for f in SOUL.md config.yaml mcp.json; do
    install_one_file "$SRC_ROOT/$f" "$DEST/$f"
  done
  install_tree "$SRC_ROOT/agent-hooks" "$DEST/agent-hooks"
  # criteria は kanban_runs 直下（実機の criteria 配置先）
  install_tree "$SRC_ROOT/criteria" "$KANBAN_RUNS_DEST" "criteria/"
  info '[step4] 完了'
}

# ---------------------------------------------------------------------------
# ⑤25役生成（hermes profile create --clone-from default ＋ souls/ から SOUL 差し替え）
# profiles.txt の各名（プレースホルダ入り）を置換した名前で25役を作る。
# ---------------------------------------------------------------------------
step5_create_profiles() {
  local profiles_file="$SRC_ROOT/profiles.txt"
  if [[ ! -f "$profiles_file" ]]; then
    die "profiles.txt が見つかりません: $profiles_file"
  fi
  info '=== step5: 25役生成 ==='
  local raw_name new_name soul_src soul_dest idx=0
  while IFS= read -r raw_name || [[ -n "$raw_name" ]]; do
    raw_name="${raw_name#"${raw_name%%[![:space:]]*}"}"
    raw_name="${raw_name%"${raw_name##*[![:space:]]}"}"
    [[ -z "$raw_name" || "$raw_name" == \#* ]] && continue
    new_name="$(replace_path "$raw_name")"
    soul_src="$SRC_ROOT/souls/$raw_name/SOUL.md"
    soul_dest="$DEST/profiles/$new_name/SOUL.md"
    idx=$((idx + 1))
    if [[ "$DRY_RUN" == "yes" ]]; then
      printf '[dry-run] (%d) hermes profile create --clone-from default %s\n' "$idx" "$new_name"
      printf '[dry-run]     SOUL: %s -> %s\n' "${soul_src#"$SRC_ROOT/"}" "$soul_dest"
      continue
    fi
    if [[ ! -f "$soul_src" ]]; then
      warn "souls/$raw_name/SOUL.md が無い（スキップ）"
      continue
    fi
    if [[ -d "$DEST/profiles/$new_name" ]]; then
      info "($idx) profile \"$new_name\" は既存のため SOUL のみ差し替えます"
    else
      hermes profile create --clone-from default "$new_name"
      info "($idx) profile \"$new_name\" を作成しました"
    fi
    mkdir -p "$(dirname "$soul_dest")"
    replace_stream < "$soul_src" > "$soul_dest"
    info "($idx) SOUL 差し替え: $soul_dest"
  done < "$profiles_file"
  info '[step5] 完了'
}

# ---------------------------------------------------------------------------
# ⑥cron jobs.json 配置（既存は .orig 退避）＋有効化手順の表示
# ---------------------------------------------------------------------------
step6_install_cron() {
  local cron_src="$SRC_ROOT/cron/jobs.json"
  local cron_dest="$DEST/cron/jobs.json"
  info '=== step6: cron jobs.json の配置 ==='
  if [[ ! -f "$cron_src" ]]; then
    die "cron/jobs.json が見つかりません: $cron_src"
  fi
  if [[ "$DRY_RUN" == "yes" ]]; then
    printf '[dry-run] cp cron/jobs.json -> %s（既存時は .orig 退避）\n' "$cron_dest"
  else
    mkdir -p "$(dirname "$cron_dest")"
    if [[ -f "$cron_dest" ]]; then
      cp -p "$cron_dest" "$cron_dest.orig"
      info "既存の jobs.json を $cron_dest.orig に退避しました"
    fi
    install_one_file "$cron_src" "$cron_dest"
  fi
  cat <<'EOF'

  [cron 有効化手順（導入先で手動実行）]
    1. hermes cron list           # 反映されたジョブ一覧の確認
    2. hermes cron enable <job-id> # 必要なジョブを個別に有効化
  （配布版 jobs.json のジョブは既定で無効状態です。全ジョブを一斉に有効化しないこと）
EOF
}

# ---------------------------------------------------------------------------
# ⑦導入確認（dry-run では実行予定チェックの表示のみ・apply では実行）
# ---------------------------------------------------------------------------
step7_verify() {
  info '=== step7: 導入確認 ==='
  local fail=0
  if [[ "$DRY_RUN" == "yes" ]]; then
    info '[dry-run] 実行予定のチェック:'
    info "[dry-run]  1. hermes profile list で25役が揃っているか"
    info "[dry-run]  2. $DEST/config.yaml / SOUL.md / mcp.json が配置されているか"
    info "[dry-run]  3. $DEST/skills / agent-hooks / cron/jobs.json が配置されているか"
    info "[dry-run]  4. criteria の配置先に criteria*.md が配置されているか"
    return 0
  fi
  # 1) profile 数（hermes profile list の行数は環境により異なるため、profiles/ の
  #    ディレクトリ数で確認する）
  local n_profiles
  n_profiles="$(ls -1 "$DEST/profiles" 2>/dev/null | wc -l || echo 0)"
  info "profiles 配置数: $n_profiles（配布 profiles.txt は 25 役）"
  if [[ "$n_profiles" -lt 25 ]]; then
    warn 'profile が 25 未満です。step5 の hermes profile create の出力を確認してください。'
    fail=1
  fi
  # 2) 主要ファイル
  local f
  for f in config.yaml SOUL.md mcp.json; do
    if [[ ! -f "$DEST/$f" ]]; then
      warn "配置先に $f がありません"
      fail=1
    fi
  done
  # 3) ディレクトリ
  for d in skills agent-hooks cron; do
    if [[ ! -d "$DEST/$d" ]]; then
      warn "配置先に $d/ がありません"
      fail=1
    fi
  done
  # 4) cron jobs.json
  if [[ ! -f "$DEST/cron/jobs.json" ]]; then
    warn '配置先に cron/jobs.json がありません'
    fail=1
  fi
  # 5) criteria
  if ! ls "$KANBAN_RUNS_DEST"/criteria*.md >/dev/null 2>&1; then
    warn "criteria 配置先に criteria*.md がありません: $KANBAN_RUNS_DEST"
    fail=1
  fi
  # 6) skills のプレースホルダが残っていないか（置換漏れチェック）
  #    検出対象は sed 置換式（[$][{]NAME[}]・build_sed_args と同じ）の通り
  #    「閉じた裸プレースホルダ」のみとする。${HERMES_HOME:-~/.hermes} 形式の
  #    シェル既定値展開は sed の置換対象外であり、正本の .md/.yaml/.json に
  #    正当に存在するため除外する（P6 裁定 2026-10-24・prefix-only の旧 BRE は
  #    これを誤検出していた。step3 detect_unknown_placeholders と同じ
  #    「接頭辞＋閉じトークン」の形に揃える）。
  local leftover prefixes_re
  prefixes_re="$(IFS='|'; printf '%s' "${PLACEHOLDER_PREFIXES[*]}")"
  leftover="$(grep -rlE --include='*.md' --include='*.yaml' --include='*.json' \
      "\\\$[{](${prefixes_re})[A-Za-z0-9_]+[}]" \
      "$DEST/skills" 2>/dev/null | head -3 || true)"
  if [[ -n "$leftover" ]]; then
    warn 'skills 内に未置換のハーネスプレースホルダが残っています（例）:'
    warn "$leftover"
    fail=1
  fi
  if [[ "$fail" -ne 0 ]]; then
    die '導入確認で問題が見つかりました（上記の WARN を確認してください）'
  fi
  info '[step7] 導入確認 OK'
}

# ---------------------------------------------------------------------------
# --replace-test モード: stdin を逆方向置換して stdout へ（配置処理なし）。
# round-trip テスト用。欠落キーは警告してスキップ（F4 の restore_content と同じ
# 挙動・値が無いプレースホルダは残る）。
# ---------------------------------------------------------------------------
run_replace_test() {
  [[ -n "$ENV_FILE" ]] || die 'replace-test モードには --env FILE が必要です（実 .env を誤って使わないため）'
  local key val entry ph
  while IFS=$'\t' read -r key val; do
    [[ "$key" == HARNESS_* ]] || continue
    RESOLVED["$key"]="$val"
  done < <(parse_env_file "$ENV_FILE")
  expand_name_map
  SED_ARGS=()
  for entry in "${PLACEHOLDER_MAP[@]}"; do
    ph="${entry%%:*}"
    key="${entry#*:}"
    val="${RESOLVED[$key]:-}"
    if [[ -z "$val" || "$val" == REPLACE_ME ]]; then
      warn "replace-test: キー欠落のため \${$ph} は置換しません: $key" >&2
      continue
    fi
    SED_ARGS+=(-e "s/[$][{]${ph}[}]/$(sed_escape "$val")/g")
  done
  replace_stream
}

# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------
usage() {
  sed -n '1,60p' "$SRC_ROOT/$(basename "${BASH_SOURCE[0]}")"
}

main() {
  local arg
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)
        MODE="dry-run"
        DRY_RUN="yes"
        ;;
      --apply)
        MODE="apply"
        ;;
      --replace-test)
        MODE="replace-test"
        ;;
      --env)
        shift
        ENV_FILE="${1:-}"
        [[ -n "$ENV_FILE" ]] || die '--env には .env ファイルのパスが必要です'
        ;;
      --skip-confirm)
        SKIP_CONFIRM="yes"
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "未知の引数: $1（--help を参照）"
        ;;
    esac
    shift
  done
  [[ -n "$MODE" ]] || die 'モードを指定してください: --dry-run | --apply | --replace-test（--help 参照）'

  if [[ "$MODE" == "replace-test" ]]; then
    run_replace_test
    return 0
  fi

  # ① hermes 導入確認
  step1_hermes_check
  # ② .env 読み込み
  step2_load_env
  # ③ 逆方向置換の準備
  step3_prepare_replacement
  # 配置先の決定（④の前に表示する）
  DEST="${PH_VALUES[HERMES_HOME]}"
  KANBAN_RUNS_DEST="${PH_VALUES[KANBAN_RUNS_DIR]}"
  info "配置先（dest）: $DEST"
  info "criteria 配置先: $KANBAN_RUNS_DEST"
  show_replacement_table

  if [[ "$MODE" == "apply" && "$SKIP_CONFIRM" != "yes" ]]; then
    printf '\n実配置を開始します（dest=%s）。よろしいですか? [y/N] ' "$DEST"
    local reply
    read -r reply
    [[ "$reply" == "y" || "$reply" == "Y" ]] || die '中止しました'
  fi

  # ④⑤⑥⑦
  step4_install_files
  step5_create_profiles
  step6_install_cron
  step7_verify
  info ''
  if [[ "$MODE" == "dry-run" ]]; then
    info 'dry-run 完了: 何も書き込んでいません。実配置するには --apply を実行してください。'
  else
    info '導入完了: cron 有効化は上記の手順（step6 の表示）に従ってください。'
  fi
}

main "$@"
