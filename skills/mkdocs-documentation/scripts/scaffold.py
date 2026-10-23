r"""MkDocs のサイト一式（mkdocs.yml・hooks・scripts・docs の雛形）をプロジェクトへ展開する。

リポジトリルートで呼ぶ。既存のファイルは上書きしない（`--force` を除く）。最後に、次に打つコマンド
（docs 依存の追加・CSS の取得・ビルド）を表示する。

    python scaffold.py --app api:create_app \\
        [--src packages/features/rooms/src --src apps/api/src ...] \\
        [--exclude-module ui] [--design-dir design] [--exclude-docs /private/ ...] \\
        [--site-name "xxx ドキュメント"] [--port 8001] [--readme-section] [--force]

- `--src` を省略すると `packages/**/src`・`apps/*/src`・`src` のうちパッケージを含むものを探す
  （凍結物・画面・試作が混ざりうるので、表示された一覧を確かめてから使う）。
- `--app` を空にすると REST API のページを作らない。
- `--design-dir` は docs/ からの相対（既定は docs/design があれば design）。
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tomllib
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
"""雛形の置き場（スキルの assets/）。"""

COPY_FILES = (
    "hooks/gen_openapi.py",
    "hooks/escape_placeholders.py",
    "hooks/exclude_nav_files.py",
    "hooks/pdf_outline.py",
    "scripts/dump_openapi.py",
    "scripts/gen_doc_pages.py",
    "docs/index.md",
    "docs/css/pdf.css",
    "puppeteer-config.json",
)
"""そのまま複写する雛形（REST API の雛形は --app があるときだけ別に足す）。"""

DEFAULT_EXCLUDE_DOCS = ("*.py", "*.toml", "*.example")
"""設計フォルダに置かれがちな、文書でないファイル。"""

GITIGNORE_LINES = ("site/", "docs/openapi/openapi.json")
"""ビルド成果物（.gitignore に足す）。"""

DOCS_PACKAGES = (
    "mkdocs>=1.6.1,<2",
    "mkdocs-material>=9.7.6",
    "mkdocstrings[python]>=1.0.4",
    "neoteroi-mkdocs>=1.2.0",
    "mkdocs-table-reader-plugin>=3.1.0",
    "mkdocs-include-markdown-plugin>=7.3.0",
    "mkdocs-mermaid-to-svg>=1.3.0",
    "mkdocs-exporter>=6.2.0",
    "mkdocs-gen-files",
    "mkdocs-literate-nav",
)
"""docs グループに入れる依存（mkdocs は 2 系を避ける。Material が 2.0 非互換を告知している）。"""


def discover_src(root: Path) -> list[str]:
    """パッケージを含む `src` を探す。

    Args:
        root: リポジトリルート。

    Returns:
        リポジトリルート相対の `src` の一覧。
    """
    skip = {".venv", "venv", "node_modules", ".git", "site", "tests"}
    found: list[str] = []
    for src in sorted(root.glob("**/src")):
        rel = src.relative_to(root)
        if any(part in skip or part.startswith(".") for part in rel.parts):
            continue
        if any((child / "__init__.py").is_file() for child in src.iterdir() if child.is_dir()):
            found.append(rel.as_posix())
    return found


def project_name(root: Path) -> str:
    """`pyproject.toml` の `project.name`（無ければフォルダ名）。

    Args:
        root: リポジトリルート。

    Returns:
        プロジェクト名。
    """
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        name = (data.get("project") or {}).get("name")
        if name:
            return str(name)
    return root.name


def render_mkdocs(args: argparse.Namespace, srcs: list[str], design_dir: str) -> str:
    """`mkdocs.yml` の雛形に値を埋める。

    Args:
        args: コマンドライン引数。
        srcs: mkdocstrings の `paths`。
        design_dir: 設計文書の置き場（docs/ 相対。無ければ空）。

    Returns:
        `mkdocs.yml` の本文。
    """
    exclude_docs = [*DEFAULT_EXCLUDE_DOCS, *args.exclude_docs]
    nav = ["  - ホーム: index.md"]
    if design_dir:
        nav.append(f"  - 設計文書: {design_dir}/")
    if args.app:
        nav.append("  - REST API: openapi/index.md")
    nav.append("  - APIリファレンス: api/")
    values = {
        "{{SITE_NAME}}": args.site_name
        or f"{project_name(Path(args.root).resolve())} ドキュメント",
        "{{PORT}}": str(args.port),
        "{{PDF_OUTPUT}}": "pdf/site.pdf",
        "{{EXCLUDE_DOCS}}": "\n".join(f"  {p}" for p in exclude_docs),
        "{{OPENAPI_APP}}": args.app,
        "{{DESIGN_DIR}}": design_dir,
        "{{EXCLUDE_MODULES}}": ", ".join(args.exclude_module),
        "{{ESCAPE_ALL_PREFIXES}}": f'"{design_dir}/"' if design_dir else "",
        "{{SRC_PATHS}}": "\n".join(f"            - {s}" for s in srcs),
        "{{NAV}}": "\n".join(nav),
    }
    text = (ASSETS / "mkdocs.yml.tmpl").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def place(target: Path, content: str | None, source: Path | None, *, force: bool) -> str:
    """1 ファイルを置く（既存は上書きしない）。

    Args:
        target: 置き先。
        content: 書く本文（`source` を複写するなら `None`）。
        source: 複写元（`content` を書くなら `None`）。
        force: 既存を上書きするか。

    Returns:
        結果の 1 語（作成・上書き・既存のため飛ばした）。
    """
    if target.exists() and not force:
        return "既存のため飛ばした"
    existed = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    if source is not None:
        shutil.copyfile(source, target)
    else:
        target.write_text(content or "", encoding="utf-8")
    return "上書き" if existed else "作成"


def main() -> int:
    """コマンドラインの入口。

    Returns:
        終了コード。
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--app", required=True, help="module:attr（REST API が無ければ空文字）")
    parser.add_argument(
        "--src", action="append", default=[], help="mkdocstrings の paths（繰り返し可）"
    )
    parser.add_argument(
        "--exclude-module", action="append", default=[], help="API リファレンスから外すモジュール名"
    )
    parser.add_argument(
        "--design-dir", default=None, help="docs/ からの相対（既定: docs/design があれば design）"
    )
    parser.add_argument(
        "--exclude-docs", action="append", default=[], help="exclude_docs に足すパターン"
    )
    parser.add_argument("--site-name", default="")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--readme-section", action="store_true", help="README にビルド手順の節を足す"
    )
    parser.add_argument("--force", action="store_true", help="既存ファイルを上書きする")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    srcs = args.src or discover_src(root)
    if not srcs:
        print("mkdocstrings の対象（src）が見つからない。--src で指定する。")
        return 1
    design_dir = (
        args.design_dir
        if args.design_dir is not None
        else ("design" if (root / "docs/design").is_dir() else "")
    )
    design_dir = design_dir.strip("/")
    if args.src == []:
        print("対象 src（自動探索。凍結物・画面・試作が混ざっていないか確かめる）:")
    for s in srcs:
        print("  ", s)

    results: list[tuple[str, str]] = []
    results.append(
        (
            "mkdocs.yml",
            place(
                root / "mkdocs.yml", render_mkdocs(args, srcs, design_dir), None, force=args.force
            ),
        )
    )
    for rel in COPY_FILES:
        results.append((rel, place(root / rel, None, ASSETS / rel, force=args.force)))
    if args.app:
        rel = "docs/openapi/index.md"
        results.append((rel, place(root / rel, None, ASSETS / rel, force=args.force)))
    for rel, result in results:
        print(f"{result:10} {rel}")

    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.is_file() else []
    missing = [line for line in GITIGNORE_LINES if line not in existing]
    if missing:
        with gitignore.open("a", encoding="utf-8") as out:
            out.write(
                "\n# MkDocs（ドキュメントサイト）のビルド成果物\n" + "\n".join(missing) + "\n"
            )
        print(".gitignore に追記:", ", ".join(missing))

    if args.readme_section:
        readme = root / "README.md"
        section = (ASSETS / "readme_section.md.tmpl").read_text(encoding="utf-8")
        section = section.replace("{{PORT}}", str(args.port)).replace(
            "{{PDF_OUTPUT}}", "pdf/site.pdf"
        )
        section = section.replace("{{DESIGN_DIR}}", design_dir or "design")
        if readme.is_file() and "ドキュメントサイト（MkDocs）" not in readme.read_text(
            encoding="utf-8"
        ):
            with readme.open("a", encoding="utf-8") as out:
                out.write(section)
            print("README.md にビルド手順の節を足した（位置は必要なら手で動かす）")

    packages = " ".join(f'"{p}"' for p in DOCS_PACKAGES)
    print("\n次に打つコマンド（リポジトリルートで）:")
    print(f"  uv add --no-sync --group docs {packages}")
    lock_diff = Path(__file__).parent / "lock_diff.py"
    print(f"  python {lock_diff}   # 既存パッケージの版が動いていないこと（追加だけ）")
    print("  uv sync --group docs --inexact")
    version_cmd = "import importlib.metadata as m; print(m.version('neoteroi-mkdocs'))"
    print(f'  V=$(uv run --group docs python -c "{version_cmd}")')
    print(
        '  curl -sSfL -o docs/css/mkdocsoad.css "https://github.com/Neoteroi/mkdocs-plugins/releases/download/v$V/css-v$V.css"'
    )
    print("  uv run --group docs playwright install chromium")
    print("  uv run --group docs mkdocs build --strict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
