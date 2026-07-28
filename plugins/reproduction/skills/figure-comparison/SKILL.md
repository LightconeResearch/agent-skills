---
name: figure-comparison
description: >
  Build a self-contained HTML report comparing original paper figures, tables,
  and reported values against reproduced artifacts in any project layout.
  Accept explicit reference and reproduction paths or discover common folders,
  pair artifacts using manifests, labels, captions, and filenames, embed images
  for portability, and flag missing or divergent results. Use when the user
  asks to compare results, build a side-by-side report, inspect reproduction
  fidelity, or determine whether a paper was reproduced.
---

# Figure comparison

Create a portable `comparison.html` that places original paper artifacts on the
left and reproduced artifacts on the right. Compare figures panel by panel,
include tables and reported values when available, and make missing or
ambiguous matches obvious.

This skill is project-system independent:

- Do not require any project-specific metadata format, workflow engine, run
  variant, or results-directory convention.
- Treat comparison manifests, target ledgers, and project metadata as optional
  hints when they happen to exist.
- Never run the reproduction pipeline. Compare only artifacts already on disk.

## Outputs

Write:

- `comparison.html` at the project root, or at the output path requested by the
  user.
- `.figure-comparison/comparison_manifest.json`
- `.figure-comparison/build_comparison.py`

Create `.figure-comparison/` if it does not exist. Do not write into the
reference or reproduced-artifact directories.

## Setup

### 1. Establish the comparison root

Use the current working directory unless the user supplied another project
root. No project marker file is required.

### 2. Resolve both sides

Prefer paths explicitly supplied by the user. Otherwise discover candidates,
shallow paths before deep recursive searches.

Reference-side candidates:

- `reference/`, `references/`, `paper/`, `original/`, `source/`
- `work/reference/`
- a directory containing paper `.tex`, `.pdf`, `document.md`,
  `metadata.json`, `figures/`, or `tables/`

Reproduced-side candidates:

- `reproduced/`, `replication/`, `outputs/`, `artifacts/`, `figures/`,
  `results/`
- populated subdirectories beneath those roots
- explicit files named in a comparison manifest or target ledger

Do not assign special semantics to directory names such as `baseline`; they are
simply possible artifact directories.

If exactly one plausible directory exists for a side, use it. If several
plausible roots remain and choosing among them would change the comparison, ask
the user which one to use. If the reproduced side is empty, continue only when
the intended output paths can be established from a manifest; otherwise ask
where the reproduced artifacts should be.

Record the resolved roots before matching anything.

### 3. Discover optional scope metadata

Use an explicitly supplied manifest first. Otherwise look for:

- `comparison-report.yaml`, `comparison-report.yml`, or
  `comparison-report.json`
- `comparison_manifest.json`
- `targets.md` or `targets/targets.md`
- project-specific result manifests or summary JSON/YAML

Project metadata may provide labels, output IDs, findings, or expected values.
It is an optional hint, never a prerequisite or the sole source of scope.

## Phase 1: Inventory the reference results

Build a reference inventory of figures, tables, and reported numerical values.

Use, in priority order:

1. Entries explicitly named by the user or scope metadata.
2. `metadata.json` or equivalent paper-artifact indices.
3. TeX labels, captions, `\includegraphics`, and table environments.
4. Markdown image/table references and nearby captions.
5. Image, table, and summary files found under the resolved reference root.

For paper prose, inspect the abstract, results, discussion, captions, and
appendices as needed. Do not read a long paper wholesale when targeted sections
provide the inventory.

For each item, preserve:

- stable label or short name
- caption or description
- reference path
- type: `figure`, `table`, or `value`
- panel or condition when one figure/value has multiple distinct parts
- expected numerical value, uncertainty, and unit when stated

If the paper is large and no manifest exists, one inventory subagent may inspect
the paper and return only the structured inventory. Do not fan out multiple
agents over the same paper.

## Phase 2: Match reproduced artifacts

Search recursively inside the resolved reproduced root. Match each reference
item using this precedence:

1. Explicit reference-to-reproduced mapping from a manifest or the user.
2. Exact label or normalized filename-stem match.
3. Caption, output-name, or nearby metadata match.
4. Strong semantic filename similarity, only when unambiguous.

Never force a weak match. If multiple candidates are plausible, record the item
as ambiguous and list the candidates in `notes`.

Supported figure formats include PNG, JPEG, PDF, EPS, SVG, and other common
image formats. Supported table/value sources include CSV, TSV, parquet,
Markdown, JSON, YAML, and plain text.

For every matched figure, inspect the original and reproduction panel by panel:

- data patterns and curve ordering
- quantities, scales, limits, and orientation
- axes, units, labels, legends, and annotations
- uncertainty bands, markers, reference lines, and omissions
- whether the same scientific conclusion follows

Do not require pixel-perfect styling. Distinguish substantive scientific
differences from cosmetic differences.

For tables, compare row/column meaning, units, values, uncertainty columns, and
omissions. For numerical values, copy values already recorded in artifacts; do
not recompute them.

## Phase 3: Build the manifest

Write `.figure-comparison/comparison_manifest.json` using this shape:

```json
{
  "project_name": "example reproduction",
  "reference_root": "reference",
  "reproduced_root": "outputs",
  "scope_source": "targets.md",
  "output_path": "comparison.html",
  "figures": [
    {
      "label": "Figure 2",
      "description": "Primary correlation result",
      "reference_path": "reference/figures/figure2.pdf",
      "reproduced_path": "outputs/figure2.png",
      "status": "matched",
      "notes": null
    }
  ],
  "tables": [
    {
      "label": "Table 1",
      "description": "Best-fit parameters",
      "reference_path": "reference/tables/table1.csv",
      "reproduced_path": "outputs/table1.csv",
      "status": "partial",
      "notes": "Uncertainty column absent in reproduction"
    }
  ],
  "values": [
    {
      "name": "primary metric",
      "paper_value": "12.5",
      "paper_uncertainty": "0.4",
      "paper_unit": "unit",
      "paper_quote": "The paper reports the primary metric.",
      "reproduced_value": "12.47",
      "reproduced_uncertainty": "0.41",
      "reproduced_value_source": "outputs/metrics.json",
      "status": "matched",
      "notes": null
    }
  ]
}
```

Paths are relative to the comparison root when possible. Use `null` when a
counterpart or field is missing. Empty figure/table/value lists are allowed and
must cause that section to be omitted from the HTML.

Allowed row statuses:

- `matched`: both sides exist and no substantive discrepancy was found
- `partial`: both sides exist but differ, or the match is ambiguous
- `missing`: either side is absent

## Phase 4: Generate the HTML

Write `.figure-comparison/build_comparison.py` and run it from the comparison
root. The helper must use the Python standard library for its core path and
read the manifest rather than deciding matches itself.

### Rendering requirements

- Produce one self-contained HTML file with inline CSS and base64-embedded
  images.
- Render one comparison card per figure, table, or value.
- Put exactly one status badge in each row header.
- Use two columns on desktop (original | reproduced) and one column on narrow
  screens.
- Include paths and captions inside their respective cells.
- Omit sections whose manifest lists are empty.
- Add a top summary counting matched, partial, and missing rows.

For PDFs, rasterize page one to PNG before embedding. Try, in order:

1. `pdf2image`
2. `pypdfium2`
3. `pdftoppm`
4. ImageMagick

If none is available, render a warning panel with the PDF path. Never embed a
PDF binary as an image data URI.

For SVG, safely embed its bytes as a data URI or rasterize it. For EPS or an
unknown image type, convert when a supported tool exists; otherwise render a
preview-unavailable panel that still records the path.

For tables, render CSV/TSV and simple text/Markdown with the standard library.
Parquet preview may use `pyarrow` or `pandas` when installed, but must degrade
gracefully to a file-exists panel.

For values, show the paper and reproduced values in the same two-cell card
layout used for figures. If numeric values and a paper uncertainty are present,
the helper may display the difference in sigma. Without an uncertainty, it may
show a simple percent difference. These are display summaries, not new
scientific results.

### Required row structure

```html
<section class="row">
  <div class="row-head">
    <div class="row-title">Figure 2 — Primary correlation result</div>
    <span class="badge badge-ok">matched</span>
  </div>
  <div class="row-grid">
    <figure class="cell">
      <div class="cell-label">ORIGINAL</div>
      <img src="data:image/png;base64,...">
      <figcaption>reference/figures/figure2.pdf</figcaption>
    </figure>
    <figure class="cell">
      <div class="cell-label">REPRODUCED</div>
      <img src="data:image/png;base64,...">
      <figcaption>outputs/figure2.png</figcaption>
    </figure>
  </div>
</section>
```

Per-cell or absolutely positioned badges are forbidden.

## Visual design

Use the Vellum aesthetic: scholarly, warm, restrained, and offline-safe.

```css
:root {
  --paper: #F2EDE5;
  --surface: #FAFAF7;
  --ink: #2E2A26;
  --ink-muted: #6B635A;
  --gold: #9A7B35;
  --teal: #4F7A6F;
  --amber: #B0823A;
  --mauve: #8A5C6B;
  --rule: #D9CFC0;
  --shadow: rgba(46, 42, 38, 0.10);
}
```

- Body: Garamond/Georgia serif, parchment background, generous outer padding.
- Code, paths, captions, and values: a mono fallback stack.
- All content inside one centered `.page` card using `--surface` and soft
  shadows.
- Status badges use teal, amber, and mauve outlines/tints rather than saturated
  fills.
- No webfonts, external assets, JavaScript, dark-mode toggle, or modern
  dashboard chrome.

## Verification

After generating:

1. Confirm `comparison.html` exists and is larger than 10 KB when it includes
   embedded figures.
2. Read back its first 50 lines.
3. Confirm every manifest row appears in the HTML.
4. Confirm each row has exactly one status badge.
5. Confirm no local absolute path is required for an embedded image to render.
6. Report the output path and counts of matched, partial, and missing figures,
   tables, and values.

Mention when an existing report was overwritten.

## Restrictions

- Do not invoke workflow engines, notebooks, recipes, training jobs, or any
  pipeline command to create missing artifacts.
- Do not modify reference artifacts, reproduced artifacts, project source, or
  scientific result files.
- Write only the requested HTML and `.figure-comparison/` working files.
- Do not fabricate values or silently resolve ambiguous matches.
- Do not copy a paper figure and present it as a reproduction.
- Do not embed images through tool-call text; let the helper read and encode
  files from disk.

## Anti-patterns

- Assuming a particular project specification, run variant, or
  `results/baseline/` layout exists.
- Asking the user to run a project-specific workflow command.
- Treating every file under a results directory as in scope.
- Matching unrelated artifacts because their filenames share a generic word.
- Reading a whole paper when targeted sections or metadata are sufficient.
- Computing new scientific results to make missing rows look complete.
- Embedding PDFs as PDFs.
- Rendering values as a single spreadsheet-like table.
- Using saturated web-app styling or omitting the centered page card.
