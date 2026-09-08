# Reference-led reproduction workflow

Use this workflow when the user names a consulting firm, supplies a reference page, or asks for high-fidelity slides or reports. Start with the actual publication, not a generic company-name theme.

## 1. Establish the reference contract

Record the official URL, title, date, format, and one-based PDF page or web exhibit number. Read the page visually. State whether the evidence is a PDF render, web exhibit, or text extraction. The initial [evidence registry](consulting-reference-evidence.json) and [comparative study](consulting-design-study.md) contain nine reviewed public documents from six firms.

Choose the intended use: projection, analytical pre-read, or reading document. Public PDFs do not establish that the source was authored in Word. Preserve the requested geometry and information roles; use the user's content and branding. Firm logos, photographs and proprietary font files are not bundled in this skill.

## 2. Measure before reproducing

Record canvas ratio and normalize all positions by page width/height. Measure the top headline band, plot origin, column widths, source area, type-size ratios and alignment anchors. Map colour to meaning: series identity, favorable/adverse result, selected option, or current/prior period. Do not merge those meanings into one generic accent.

For every page, define: assertion headline; chart title or scope; unit and period; chart/table structure; direct labels; interpretation; source; limitations. A copied visual hierarchy with altered or untraceable numbers is not a faithful analytical reproduction.

## 3. Select an implementation route

| Need | Supported route |
| --- | --- |
| Projected presentation | Existing 22 SVG patterns, standard layout |
| Analytical pre-read | `layout: analytical`, fixed 32px assertion headline, optional `exhibit_label`, scope in `subline` |
| Chart with interpretation rail | `distribution` plus `commentary: {title, points}`; up to six bars and three short points |
| Consistent colour meaning | `palette: navy`, `red`, `green`, or `mono`; these are original semantic presets, not official brand colours |
| Figure integrated into a document | `render_slide_spec.py --exhibit` or report `exhibit_mode: compact` |
| One-column reading brief | HTML `report_style: briefing`; no forced cover page or TOC |
| Editorial reading document | HTML `report_style: editorial`; A4 print cover, TOC, two-column prose, full-width figures and tables |
| Editable Word brief | Optional `build_briefing_docx.cjs`; native paragraphs, heading styles and tables; vector figure with PNG fallback |
| Complex mixed charts, free-positioned annotations, original branded masters | Still custom work. Do not call an approximation an exact reproduction |

The analytical header reserves y=40 for identification, y=88/128 for a maximum two-line assertion, and y=163 for scope. Main chart content starts at y=208 on a 1280×720 canvas. The commentary chart uses x=80–828 for data and x=896–1200 for interpretation. This is an implemented starting grid, not a measured universal consulting standard.

Compact exports use the chart body only. Captions, scope, notes and sources are placed in the host document, with the sidebar interpretation converted to editable prose. Exported chart images still require regeneration from JSON to change the data. Native editable Office charts are not implemented.

## 4. Build and edit the samples

From the installed skill directory:

```bash
python3 scripts/render_slide_spec.py templates/reference-layouts/capacity-briefing.json -o slide.svg
python3 scripts/build_html_report.py templates/reference-layouts/decision-brief.md -o brief.html
```

Word export is optional and requires Node.js packages `docx` and `sharp`, plus Python 3. Install those packages in the environment used to run the exporter. The existing SVG and HTML pipeline remains Python-standard-library only.

```bash
node scripts/build_briefing_docx.cjs templates/reference-layouts/decision-brief.json -o brief.docx
```

Word input is a JSON object with `title`, optional `subtitle`, `author`, `date`, `classification`, `running_title`, and `blocks`. Supported block shapes:

```json
{
  "title": "Decision brief",
  "blocks": [
    {"type": "heading", "text": "Recommendation"},
    {"type": "paragraph", "text": "Write a complete recommendation."},
    {"type": "exhibit", "spec": "chart.json", "caption": "State what the evidence shows"},
    {"type": "table", "headers": ["Action", "Owner"], "rows": [["Validate capacity", "Operations"]]}
  ]
}
```

Spec paths resolve relative to the input JSON. Tables support one to six equal-width columns; use short cell content. Prose is plain text, not Markdown. This exporter is a one-column A4 briefing tool, not a general Word conversion engine. Word and HTML source files are separate editable inputs; update both when maintaining paired outputs.

## 5. Evaluate the reproduction

Use a 0–2 score for each dimension: narrative hierarchy, frame geometry, type hierarchy, chart encoding, annotation/labels, source/notes, page flow, editability. Zero means missing or incorrect; one means approximate; two means reference-aligned and verified. A proposed acceptance target is at least 14/16, with no zero for chart encoding, labels or source. This is a target rubric, not a measured score for the current templates.

Inspect the rendered output beside the selected reference at equal width. Check changes in units, arithmetic, signs, sorting, axis baseline, labels, line breaks, source placement and page breaks. Record which aspects match and which differ. Do not claim pixel-level fidelity from a code test alone. Test corner cases and report them separately from the visual review.

For Word, reopen the file in an Office-compatible renderer and inspect every output page. For HTML, verify desktop, narrow-screen and print layouts. Shorten or restructure content when the page becomes unbalanced; do not silently reduce type until it fits.

## HTML to PDF

Use JSON for charts and Markdown for the narrative. Generate HTML, review it in the browser, and export that same HTML to PDF. HTML is the primary layout artifact; Word is an optional separate export. Reports use A4 print styles; decks use one 16:9 slide per page.

```bash
python3 -m pip install playwright
python3 scripts/build_html_report.py templates/reference-layouts/decision-brief.md -o brief.html
python3 scripts/export_pdf.py brief.html -o brief.pdf
python3 scripts/export_pdf.py examples/demo-deck.html -o deck.pdf
```

PDF export requires installed Google Chrome or Chromium (`--browser /path/to/browser` for a custom executable). SVG and HTML generation remain Python-standard-library only. Alternatively, open the generated HTML, choose **Save as PDF**, and select the browser’s PDF destination. Inspect every page after changing content; longer reports may need deliberate page breaks.
