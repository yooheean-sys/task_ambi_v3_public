# JP patent specification format (JPO) — tooling rules

## Hard format rules (JPO official guidance)

- **Paragraph numbers**: 【０００１】 full-width 4-digit, sequential through the description; placed AFTER each heading; NEVER after numbered items (【特許文献１】, 【非特許文献１】, 【化１】, 【数１】, 【表１】, 【図１】).
- **Fixed heading order** per the 様式: 【技術分野】→【背景技術】→【先行技術文献】→【発明の概要】→【発明が解決しようとする課題】→【課題を解決するための手段】→【発明の効果】→【図面の簡単な説明】→【発明を実施するための形態】→【産業上の利用可能性】→【符号の説明】. Encode the order in the outline template and lint it.
- **Character constraints**: half-width katakana prohibited; 【 】 and ▲▼ are reserved characters (usable only in their designated positions); charset limited to JIS X 0208 (no circled numbers etc.). Run a charset/reserved-character lint on the SOURCE before conversion.
- **Presentation**: MS Mincho-class Japanese fonts, 10–12pt equivalents; plain である style; publications must not substitute for disclosure. Chemical formulas and equations appear as numbered items 【化１】/【数１】 (as figures or limited text) — do NOT rely on OMML math conversion for patents.

## Pipeline

1. Derive `reference.docx` ONCE from the patent firm's Word template (fonts, margins, style mapping). This is where presentation rules live, not in manual Word edits.
2. Draft in markdown, **claims first** (請求項), then embodiments; maintain the reference-numeral table (符号表) in `spec/notation.md`.
3. Generate 段番号 and headings with a deterministic postprocess step (Lua filter or python-docx script) — never hand-number, never bulk-fix in Word GUI.
4. Run the patent lint set (charset, reserved chars, style, claim-term support) BEFORE conversion. Word is only for final visual check and hand-off to the attorney.

## Why this shape

- Manual Word post-processing sits outside the automation chain: every regeneration resurrects the manual work, and the fixes leave no record in git. Moving the rules into reference.docx + scripts makes the DOCX correct at conversion time and the whole chain reproducible.
