---
type: entity
title: "assets: canned report (assets/report/)"
slug: assets-report
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["report", "weasyprint", "jinja", "athena", "assets"]
---

# assets: canned report (`assets/report/`)

Canned report generation assets, deployed via `CapeCannedReports` (see
[[entities/capemeta-module]]) and served through the `get_canned_report` API
handler (see [[entities/assets-capi-handlers]]).

## `bactopia-single-sample-analysis/`

### `data_function.py`

- A Lambda that retrieves the data for a bactopia single-sample analysis report.
- Uses `awswrangler` (`wr`) to run Athena queries against the data lake. It
  holds SQL templates (`METADATA_QRY_TEMPLATE`, `SPECIES_INFO_QRY_TEMPLATE`,
  etc.) that join cleaned tables (sample metadata, `result_software_versions`,
  `result_sourmash_gtdb_...`) keyed by `sample_id`.
- TODO notes: needs a layer with weasyprint + jinja2; currently transitioning
  from fake data to real Athena-backed data keyed by an incoming job id.

### `template.html.j2`

- The Jinja2 HTML template for the report, rendered and (per the report-gen
  layer) turned into a PDF via WeasyPrint. See [[entities/assets-lambda-layers]]
  (`report-gen`).

Related: [[syntheses/assets-subsystem]], [[entities/capemeta-module]].
