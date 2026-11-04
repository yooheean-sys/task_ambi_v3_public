---
name: longform-writing-pipeline
description: "Use when planning agent-assisted long-form document writing."
version: "1.0.0"
license: MIT
metadata:
  hermes:
    tags: [writing, documentation, publishing]
---

# Agent-assisted long-form writing pipeline

Scope: setting up and running the writing pipeline for papers, research reports, and patent specifications with Hermes agents. Topical depth lives in references/.

**User context**: Japanese documents + English papers, WSL, single-to-few authors, Hermes kanban/SDD orchestration. Machine-verifiable QA and reproducibility outrank editor comfort.

## When to Use

Load this skill when the user asks how to structure, tool, or automate writing of long documents (papers, research reports, patent specifications), when recommending writing/publishing tooling (LaTeX, Quarto, Pandoc, Typst, Sphinx, Overleaf, linters, citation tooling), or when setting up a writing repository or drafting skills. For one-off short answers about a single tool's usage, general knowledge suffices; engage this skill when the deliverable is a writing pipeline or a tooling decision.

## Three-layer architecture (always)

1. **Spec layer** — human-approved BEFORE any prose is written:
   - `spec/outline.md`: per section — purpose, key claims, citation keys, word budget, done-criteria. This is the writing equivalent of a spec-kit spec.
   - `spec/glossary.md` + `spec/notation.md`: canonical terms, math symbols, patent reference numerals. Terminology drift is the #1 cross-section failure mode.
   - `spec/style.md`: rules that mirror the lint config — one source of truth, never two divergent rule sets.
2. **Manuscript layer** — one file per section (`manuscript/00_intro.md` …). Small files keep diffs reviewable, drafting parallel, and review partial.
3. **Verification layer** — one command each, wired into just/Makefile: `lint`, `check-refs`, `coverage`, `build`.

Human gates: (1) outline + glossary approval before drafting starts; (2) full-read approval after integration, always reviewed via diff (latexdiff / git diff).

## Agent loop per section (kanban card = one section)

draft from outline → run lint + consistency checks → fix → render (HTML for iteration) → human reviews the diff → apply feedback as targeted patch.

## Format choice

Default canonical: markdown-family via Quarto — one source → PDF/HTML/DOCX/slides. See `references/format-selection.md` for the decision table and fallbacks (LaTeX direct writing for Overleaf-locked co-authors or unsupported journal classes; Sphinx only for web-delivered docs; patents via reference.docx + postprocess — see `references/patent-jpo-format.md`).

## Verification stack

textlint (Japanese) / Vale (English) / citation-existence gates / glossary+coverage checks — see `references/verification-stack.md`. Never insert a citation from model memory.

## Speckit mapping (when asked "is there a spec-kit for writing?")

constitution→style/glossary; specify+plan→outline; tasks→one section = one card; implement→section drafting; analyze→consistency+coverage checks. No mature generic writing spec-kit exists (closest: STORM for outline-from-sources article generation, bookwright for fiction) — build the mapping as Hermes skills instead of hunting for a silver bullet. Implemented 2026-11-04 as longform-project-init / longform-outline / longform-section-draft / longform-revise / longform-integrate.

## Pitfalls

- Manual Word/format post-processing outside the pipeline resurrects on every regeneration — bake 様式 into reference.docx and deterministic postprocess scripts instead.
- Whole-section regeneration destroys reviewable diffs — revise by targeted patch, never full rewrite.
- Agents cannot hit length targets unaided — put word budgets in the outline and measure with wc.
- Long documents: iterate on HTML preview, render PDF only at release — full LaTeX compile of large documents is slow.
- Citation fabrication is the top LLM failure mode — the bib existence gate is the defense, not prompt politeness.

## References

- `references/format-selection.md` — decision table per document type + verified tool facts
- `references/verification-stack.md` — lint presets, citation gates, consistency checks
- `references/patent-jpo-format.md` — JPO 様式 rules and the DOCX pipeline
- `references/skill-set.md` — 実行スキル5点の分担設計(責務・入出力・停止点)。決定論チェックは justfile、判断とゲートだけをスキルに
