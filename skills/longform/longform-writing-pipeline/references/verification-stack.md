# Prose QA and citation integrity stack

## Lint selection

- **Japanese: textlint is the standard.** Use `textlint-rule-preset-jtf-style` (JTF style guide), `textlint-rule-preset-ja-technical-writing`, and `textlint-rule-prh` — prh's dictionary doubles as glossary enforcement (forbidden synonyms, mandatory fixed terms).
- **English: Vale** with a pinned style package. Vale parses markup, so code blocks and URLs are skipped; it runs natively on .qmd/MyST/RST/AsciiDoc/Typst but NOT LaTeX — lint markdown sources, never generated .tex.
- **Grammar supplement**: LanguageTool (self-hostable server) catches what rule-based linters miss; its Japanese quality is weaker than textlint rules, so use it for English.
- Wire everything into ONE command (`just lint`) so the agent loop is: draft → lint → fix → render. An agent can run a single command; it cannot reliably run six.

## Citation integrity (top LLM failure mode)

- A bib key enters `references.bib` only after existence verification (Crossref/OpenAlex/DOI lookup). Bibliographic data recalled from model memory is never trusted.
- Every factual sentence carries a `[@key]` anchor; the build fails on unresolvable keys, which mechanically bounds fabrication instead of relying on prompt discipline.
- Zotero + Better BibTeX auto-export keeps `.bib` synchronized from a human-curated library.
- Coverage check: every outline claim maps to at least one anchor in the manuscript; reverse-scan for orphan claims (prose without anchors).

## Consistency checks

- Glossary scan: grep the manuscript for synonyms of canonical terms (prh rules make this mechanical).
- Notation scan: the notation table drives symbol-consistency greps (math symbols for papers, reference numerals for patents).
- Outline reverse-lookup: every outline claim must appear in the manuscript; flag sections whose content drifts from the approved outline.
