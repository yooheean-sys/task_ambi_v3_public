"""MkDocs の gen-files スクリプト: API リファレンスと設計図・表のページをビルド時に生成する。

生成するのはビルド時だけの仮想ファイルで、リポジトリには書き込まない。設定は `mkdocs.yml` から読む。

- `api/`: 1 モジュール 1 ページ（`::: <モジュール>`）と、literate-nav 用の `api/SUMMARY.md`。対象は
  mkdocstrings の `paths`（各パッケージの `src`）配下。`_` で始まる private と、
  `extra.docs_build.exclude_modules`（画面など）は除く。
- `{design_dir}/`: `.mmd` を mermaid フェンスで、`.csv` を `read_csv` で包むページと、
  既存の `.md` を合わせた literate-nav 用の `{design_dir}/SUMMARY.md`
  （`extra.docs_build.design_dir` が空なら作らない）。

`mkdocs.yml` の `plugins.gen-files.scripts` から呼ばれる。
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files
from mkdocs_gen_files.editor import FilesEditor

CONFIG = FilesEditor.current().config
"""実行中の MkDocs の設定。"""

ROOT = Path(CONFIG.config_file_path).resolve().parent
"""`mkdocs.yml` のある場所（リポジトリルート）。"""

SETTINGS: dict = (CONFIG.extra or {}).get("docs_build") or {}
"""雛形が読む設定（`extra.docs_build`）。"""

SRC_ROOTS: tuple[Path, ...] = tuple(
    ROOT / p for p in CONFIG.plugins["mkdocstrings"].config["handlers"]["python"]["paths"]
)
"""API リファレンスの対象（mkdocstrings の `paths` と同じ並び）。"""

EXCLUDED_MODULES = frozenset(SETTINGS.get("exclude_modules") or ())
"""API リファレンスから外すモジュール名。"""

DESIGN_REL = (SETTINGS.get("design_dir") or "").strip("/")
"""設計文書の置き場（`docs_dir` からの相対）。空なら設計文書のページを作らない。"""

DOCS_DIR = Path(CONFIG.docs_dir)
"""`docs_dir` の絶対パス。"""


def module_targets(src_root: Path) -> list[tuple[tuple[str, ...], bool]]:
    """`src` 配下で API リファレンスに載せるモジュールを列挙する。

    Args:
        src_root: パッケージの `src` ディレクトリ。

    Returns:
        `(ドット区切りの各部, パッケージか)` の一覧（パス順）。
    """
    targets: list[tuple[tuple[str, ...], bool]] = []
    for path in sorted(src_root.rglob("*.py")):
        parts = path.relative_to(src_root).with_suffix("").parts
        is_package = parts[-1] == "__init__"
        if is_package:
            parts = parts[:-1]
        if not parts or any(part.startswith("_") for part in parts):
            continue
        if parts[-1] in EXCLUDED_MODULES:
            continue
        targets.append((parts, is_package))
    return targets


def write_api_pages() -> None:
    """API リファレンスのページと `api/SUMMARY.md` を生成する。"""
    nav = mkdocs_gen_files.Nav()
    for src_root in SRC_ROOTS:
        for parts, is_package in module_targets(src_root):
            rel = Path(*parts, "index.md") if is_package else Path(*parts).with_suffix(".md")
            dotted = ".".join(parts)
            nav[parts] = rel.as_posix()
            with mkdocs_gen_files.open(Path("api", rel), "w") as page:
                page.write(f"# {dotted}\n\n::: {dotted}\n")
    with mkdocs_gen_files.open("api/SUMMARY.md", "w") as summary:
        summary.writelines(nav.build_literate_nav())


def wrapper_page(source: Path) -> str:
    """設計図（`.mmd`）・表（`.csv`）を包むページの本文を組み立てる。

    Args:
        source: 設計文書の置き場の配下の `.mmd` か `.csv`。

    Returns:
        ページの Markdown。図は mermaid フェンスへ include-markdown で、表は `read_csv` で取り込む。
        include-markdown は取り込む側のファイルからの相対でパスを解決するが、生成ページは一時
        ディレクトリに置かれるので、図は絶対パスで指す。表のパスは `mkdocs.yml` からの相対。
    """
    rel_root = source.relative_to(ROOT).as_posix()
    header = f"# {source.stem}\n\n出典: `{rel_root}`\n\n"
    if source.suffix == ".mmd":
        return f'{header}```mermaid\n{{% include-markdown "{source.as_posix()}" %}}\n```\n'
    return f"{header}{{{{ read_csv('{rel_root}') }}}}\n"


def design_entries(directory: Path, design_dir: Path, depth: int) -> list[str]:
    """1 フォルダ分の literate-nav の行を作る（必要ならラッパーページも生成する）。

    Args:
        directory: 設計文書の置き場の配下のフォルダ。
        design_dir: 設計文書の置き場（絶対パス）。
        depth: ナビの入れ子の深さ（0 が置き場の直下）。

    Returns:
        `SUMMARY.md` に書く行の一覧（ファイルを名前順、続いてサブフォルダを名前順）。

    Raises:
        FileExistsError: ラッパーページと同名の `.md` が既にある。
    """
    indent = "    " * depth
    lines: list[str] = []
    for path in sorted(p for p in directory.iterdir() if p.is_file()):
        rel = path.relative_to(design_dir)
        if path.suffix == ".md" and path.name != "SUMMARY.md":
            lines.append(f"{indent}* [{path.stem}]({rel.as_posix()})\n")
        elif path.suffix in (".mmd", ".csv"):
            page = rel.with_suffix(".md")
            if (design_dir / page).exists():
                msg = f"ラッパーページと同名の md が既にある: {design_dir / page}"
                raise FileExistsError(msg)
            with mkdocs_gen_files.open(Path(DESIGN_REL, page), "w") as out:
                out.write(wrapper_page(path))
            kind = "図" if path.suffix == ".mmd" else "表"
            lines.append(f"{indent}* [{path.stem}（{kind}）]({page.as_posix()})\n")
    for sub in sorted(p for p in directory.iterdir() if p.is_dir() and not p.name.startswith(".")):
        sub_lines = design_entries(sub, design_dir, depth + 1)
        if sub_lines:
            lines.append(f"{indent}* {sub.name}\n")
            lines.extend(sub_lines)
    return lines


def write_design_pages() -> None:
    """設計図・表のラッパーページと `{design_dir}/SUMMARY.md` を生成する。"""
    if not DESIGN_REL:
        return
    design_dir = DOCS_DIR / DESIGN_REL
    if not design_dir.is_dir():
        return
    with mkdocs_gen_files.open(f"{DESIGN_REL}/SUMMARY.md", "w") as summary:
        summary.writelines(design_entries(design_dir, design_dir, 0))


write_api_pages()
write_design_pages()
