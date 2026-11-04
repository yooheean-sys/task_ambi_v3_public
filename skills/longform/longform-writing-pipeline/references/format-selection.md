# Format selection for long-form documents

## Decision table

| Document type | Canonical | Build | Fallback |
|---|---|---|---|
| Academic paper (journal submission) | Quarto (.qmd) when the venue is covered by a journal template | `quarto render` → PDF with `cite-method: natbib`/`biblatex`; `keep-tex: true` for arXiv/latexdiff | LaTeX direct (latexmk) when co-authors are Overleaf-locked or the journal class is unsupported |
| Research report / internal document | Quarto | PDF/HTML/DOCX; math becomes native Word equations (OMML) | — |
| Patent specification (JP) | Quarto / plain markdown | DOCX via `reference.docx` + deterministic postprocess (段番号, headings) | Patent firm's Word template |
| Web technical documentation | Sphinx/MyST | sphinx build | Quarto website |

## Verified tool facts

- **Overleaf git integration is premium-only** and is not a real git repo: no branches, tags, or symlinks; commits mirror Overleaf's internal history. For agent-driven writing prefer local latexmk/Quarto + git; use Overleaf only as the co-author web editor. (docs.overleaf.com)
- **Quarto journal templates**: the official quarto-journals GitHub org covers ACM, ACS, Elsevier, MIT; community extensions add Springer Nature (natbib styles, referee/lineno options), ASCE, and others. Template quality varies — the Elsevier template needed an include-in-header workaround for citation rendering. (quarto.org, github.com/quarto-journals)
- **Quarto citations**: PDF can use natbib/biblatex, DOCX/HTML use citeproc+CSL — rendering can differ across outputs unless a matching CSL is chosen. (quarto.org)
- **Quarto book projects** assemble chapter files with cross-chapter cross-references (`@fig-`/`@tbl-`/`@sec-` resolve with chapter numbers); part/appendix/number-depth are configurable. (quarto.org/docs/books)
- **Vale does not parse LaTeX** (upstream won't-fix); it runs natively on Markdown, MyST, Quarto, AsciiDoc, Typst, RST, HTML. Lint the source, not generated .tex. (docs.vale.sh)
- **Typst** is the emerging PDF engine (Quarto bundles the orange-book format for book projects); journal acceptance is still narrow — verify per venue before committing.
- **Writing-side spec-kit analogs**: STORM (stanford-oval/storm, arXiv 2402.14207) for outline-from-sources, citation-grounded article generation; bookwright (jmorenobl/bookwright) for spec-driven fiction authoring with continuity validation. No mature general-purpose writing spec-kit exists.

## Migration notes

- markdown→LaTeX via pandoc preserves structure but journal-specific commands need hand-work; choose the canonical format by the strictest target output, not the easiest.
- Avoid hybrid workflows (draft in markdown, then re-typeset in LaTeX by hand) — they create dual sources of truth that drift.
