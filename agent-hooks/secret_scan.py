#!/usr/bin/env python3
"""F10 相当の機密スキャン（pre-commit hook 本体・P6/F14）。

根拠: 正本リポジトリ docs/harness_migration_plan.md
  - L167: 機密スキャン（置換対象語・実パス・組織名・社名が0件）を pre-commit で自動化
  - L179: 検査語リストは人名・組織名・社名も含める
  - L185: 検査語リストに .env の値群も含める

語群の単一ソース（計画 §5 D3「置換テーブル単一化」）は正本
${REPO_NAME}/scripts/harness_replacements.py（F4 テーブル）と
make_harness_public.py（F10 機密語リスト）。正本が見つからない環境
（他者が公開リポジトリを clone した場合など）では、リポジトリの .env 実値
（.env.EXAMPLE と共有される雛形値は除外）と内蔵の汎用正規表現による
劣化モードで代替走査する。機密語リスト自体は公開リポジトリに含めない。

走査対象:
  - 引数で渡されたファイル（pre-commit はステージされたファイルを渡す）
  - --all 指定時は git ls-files の全追跡ファイル（最終検査モード）
  - ファイル内容に加え、相対パス名も語群で検査する（F10 同様）

保護機能:
  - .env 自体のステージ/コミットを強制失敗させる（L185 の二重防護の1つ）
  - 機密語の値そのものは出力しない（env 値・汎用トークンは種別のみ報告）

出力: 「相対パス:行番号: 種別」形式。終了コード 0=検出0件 / 1=検出あり。
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 正本リポジトリの場所（リテラル名は公開リポジトリに置かない。決定順序:
#   1) 環境変数 TASK_AMBI_HARNESS_REPO
#   2) .env の HARNESS_REPO_NAME（導入先の実値から復元）
#   3) 兄弟ディレクトリの探索（scripts/harness_replacements.py を持つ隣接リポジトリ）
def _default_canonical_scripts() -> Path:
    env_path = REPO_ROOT / ".env"
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("HARNESS_REPO_NAME="):
                name = line.partition("=")[2].strip().strip('"').strip("'")
                if name:
                    return REPO_ROOT.parent / name / "scripts"
    if env_path.is_file():
        for sibling in sorted(REPO_ROOT.parent.iterdir()):
            cand = sibling / "scripts"
            if (cand / "harness_replacements.py").is_file() \
                    and (cand / "make_harness_public.py").is_file() \
                    and (sibling / "docs" / "harness_migration_plan.md").is_file():
                return cand
    return REPO_ROOT.parent / "scripts"  # 見つからなければ劣化モードへ


CANONICAL_SCRIPTS = Path(
    os.environ.get("TASK_AMBI_HARNESS_REPO", _default_canonical_scripts())
)

# .env / .env.EXAMPLE は実値を保つ対象であり、走査対象ファイルからは除外する
# （.env は .gitignore 済み。ステージされた場合は後段で強制失敗とする）
PROTECTED_FILE_NAMES = {".env"}

# 正本の語群に含まれる「単独語」と、その部分一致（例: ${REPO_NAME}_public）
# を区別するため F10 と同じ単語境界正規表現を使う
_BOUNDARY = r"(?<![A-Za-z0-9_]){}(?![A-Za-z0-9_])"

# 正規走査で検出値を秘匿する種別接頭辞（値そのものは出力しない）
ENV_KIND = "env-value:{}"  # .env の KEY 名のみ表示
BUILTIN_KINDS = {
    "private-ip": re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "openai-like-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "slack-webhook": re.compile(r"https://hooks\.slack\.com/services/\S+"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "private-key-block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}

# 汎用「実パス」検出で除外する説明用ユーザ名（スキル文書の例示に使用）
DOC_EXAMPLE_USERS = {
    "user", "me", "youruser", "username", "example", "www", "root",
    "Public", "Default", "All Users", "you", "yourname",
}


# ------------------------------------------------------------- 正本語群 ----
def load_canonical():
    """正本の F4 テーブル + F10 機密語リストを読む。無ければ (None, 理由)。"""
    if not CANONICAL_SCRIPTS.is_dir():
        return None, f"canonical scripts dir not found: {CANONICAL_SCRIPTS}"
    try:
        sys.path.insert(0, str(CANONICAL_SCRIPTS))
        hr = importlib.import_module("harness_replacements")
        mp = importlib.import_module("make_harness_public")
    except Exception as exc:  # pragma: no cover - 環境差の報告用
        return None, f"canonical import failed: {exc}"
    return (hr, mp), "ok"


def canonical_placeholder_var(canonical) -> re.Pattern | None:
    """F10 と同じ「プレースホルダ変数名」抑止正規表現を組み立てる。"""
    hr, mp = canonical
    words = sorted({*hr.REPLACEMENTS, *mp.SUPPLEMENTARY_REPLACEMENTS}, key=len, reverse=True)
    case_sensitive = {w for w in words if w not in hr.CASE_INSENSITIVE_KEYS}
    stems = [re.escape(w) for w in case_sensitive if len(w) >= 4]
    if not stems:
        return None
    return re.compile(r"(?i)HARNESS_[A-Z0-9_]*(?:%s)" % "|".join(stems))


# ------------------------------------------------------------ .env 値群 ----
def load_env_words() -> list[tuple[str, str]]:
    """リポジトリ .env の実値を走査語にする（L185）。

    .env.EXAMPLE の本文に同一文字列が現れる値（雛形と共有される値・プレース
    ホルダ）は機密ではないため除外する。戻り値は (KEY, 値) — 値は報告時に
    出力しない。
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return []
    example = ""
    example_path = REPO_ROOT / ".env.EXAMPLE"
    if example_path.is_file():
        example = example_path.read_text(encoding="utf-8")
    words: list[tuple[str, str]] = []
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if len(value) < 4 or "REPLACE_ME" in value:
            continue
        if value in example:  # 雛形と共有される値は機密ではない
            continue
        words.append((key.strip(), value))
    return words


# --------------------------------------------------------------- 走査本体 ----
def iter_lines(path: Path):
    data = path.read_bytes()
    if b"\x00" in data:  # バイナリは走査対象外（F10 同様）
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    for lineno, line in enumerate(text.splitlines(), 1):
        yield lineno, line


def generic_path_regex_hits(line: str) -> list[str]:
    """内蔵の実パス検出。説明用ユーザ名は除外する。"""
    hits = []
    for m in re.finditer(r"/home/([A-Za-z0-9][A-Za-z0-9._-]*)/", line):
        if m.group(1) not in DOC_EXAMPLE_USERS:
            hits.append("builtin:real-home-path")
    for m in re.finditer(r"C:\\Users\\([^\\]+)\\", line):
        name = m.group(1)
        if name not in DOC_EXAMPLE_USERS and "{" not in name:
            hits.append("builtin:windows-user-path")
    for m in re.finditer(r"/Users/([A-Za-z0-9][A-Za-z0-9._-]*)/", line):
        if m.group(1) not in DOC_EXAMPLE_USERS:
            hits.append("builtin:macos-user-path")
    return hits


def scan_file(path: Path, rel: str, word_regexes, scan_regexes,
              placeholder_var, env_word_regexes) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    # --- パス名走査（F10 同様） ---
    path_inspected = re.sub(r"\$\{[^}]*\}", " ", rel)
    if placeholder_var is not None:
        path_inspected = placeholder_var.sub(" ", path_inspected)
    for label, rx in word_regexes:
        if rx.search(path_inspected):
            hits.append((rel, 0, f"path:word:{label}"))
    for label, rx in scan_regexes:
        if rx.search(path_inspected):
            hits.append((rel, 0, f"path:regex:{label}"))
    # --- 内容走査 ---
    for lineno, line in iter_lines(path):
        inspected = re.sub(r"\$\{[^}]*\}", " ", line)
        if placeholder_var is not None:
            inspected = placeholder_var.sub(" ", inspected)
        for label, rx in word_regexes:
            if rx.search(inspected):
                hits.append((rel, lineno, f"word:{label}"))
        for label, rx in scan_regexes:
            if rx.search(line):
                hits.append((rel, lineno, f"regex:{label}"))
        for key, rx in env_word_regexes:
            if rx.search(line):
                hits.append((rel, lineno, ENV_KIND.format(key)))
        for label in generic_path_regex_hits(line):
            hits.append((rel, lineno, label))
        for label, rx in BUILTIN_KINDS.items():
            if rx.search(line):
                hits.append((rel, lineno, f"builtin:{label}"))
    return hits


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return [f for f in out.stdout.splitlines() if f]


# ------------------------------------------------------------------ main ----
def main(argv: list[str]) -> int:
    canonical, why = load_canonical()
    word_regexes: list[tuple[str, re.Pattern]] = []
    scan_regexes: list[tuple[str, re.Pattern]] = []
    placeholder_var = None
    canonical_scan = None
    if canonical is not None:
        hr, mp = canonical
        words = sorted({*hr.REPLACEMENTS, *mp.SUPPLEMENTARY_REPLACEMENTS}, key=len, reverse=True)
        case_insensitive = set(hr.CASE_INSENSITIVE_KEYS)
        for w in words:
            rx_body = _BOUNDARY.format(re.escape(w))
            word_regexes.append(
                (w, re.compile(rx_body) if w not in case_insensitive
                 else re.compile(rx_body, re.IGNORECASE))
            )
        scan_regexes = list(mp.SCAN_REGEXES)
        placeholder_var = canonical_placeholder_var(canonical)
        canonical_scan = mp.scan_public
        print(f"[scan] 正本語群: 取り込み済み (F4+F10 語群 {len(words)} 語)"
              f" ← {CANONICAL_SCRIPTS}")
    else:
        print(f"[scan] 正本語群: なし（{why}）→ 劣化モード"
              "（.env 実値 + 内蔵汎用正規表現で走査）")

    # L185: .env の値群を検査語に加える（雛形共有値は除外）
    env_word_regexes = [
        (key, re.compile(_BOUNDARY.format(re.escape(value))))
        for key, value in load_env_words()
    ]
    if env_word_regexes:
        print(f"[scan] .env 実値を検査語に追加: {len(env_word_regexes)} 語"
              "（雛形共有値は除外・KEY 名のみ報告）")

    # 対象ファイル決定
    if "--all" in argv:
        args = [a for a in argv if a != "--all"]
        files = tracked_files()
        mode = "all-tracked-files"
    else:
        args = argv
        files = list(args)
        mode = "given-paths"
    files = [f for f in files if f not in PROTECTED_FILE_NAMES]

    hits: list[tuple[str, int, str]] = []
    # .env 保護: ステージ/指定された .env は常に失敗（L185 二重防護）
    protected_staged = [a for a in args if Path(a).name in PROTECTED_FILE_NAMES]
    for p in protected_staged:
        hits.append((p, 0, "protected-file:.env はコミット禁止"))

    if files:
        if canonical_scan is not None:
            # 正本 F10 scan_public をリポジトリ全体に実行し、対象ファイルに
            # 関するヒットのみ採用（F10 との完全一致を保証。.env は非追跡で
            # 除外されるため実値は走査対象に載らない）
            for rel, lineno, kind in canonical_scan(REPO_ROOT):
                if rel in set(files) or (lineno == 0 and rel in set(files)):
                    hits.append((rel, lineno, f"F10:{kind}"))
        file_set = set(files)
        for rel in files:
            p = REPO_ROOT / rel
            if not p.is_file() or p.is_symlink():
                continue
            hits.extend(scan_file(p, rel, word_regexes, scan_regexes,
                                  placeholder_var, env_word_regexes))
        del file_set

    print(f"[scan] mode={mode} files={len(files)}")
    if hits:
        print(f"[scan] 検出 {len(hits)} 件 — commit を中止してください:")
        for rel, lineno, kind in hits:
            print(f"  {rel}:{lineno}: {kind}")
        return 1
    print("[scan] 機密語 0 件（置換対象語・実パス・組織名・社名・.env 実値）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
