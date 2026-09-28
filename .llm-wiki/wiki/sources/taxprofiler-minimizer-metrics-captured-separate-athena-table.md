---
type: source
title: Taxprofiler minimizer metrics captured separately
status: insight
category: etl
created: 2026-09-28
updated: 2026-09-28
slug: taxprofiler-minimizer-metrics-captured-separate-athena-table
---

# Taxprofiler minimizer metrics captured separately

The local ETL now preserves optional Kraken2 minimizer metrics without changing the report-facing `kraken2_taxa` schema. It writes `kraken2_minimizers/sample_id=<sample>/database_id=<db>/minimizers.csv`, which the existing result crawler should expose as `result_kraken2_minimizers`; six-column reports overwrite this key with a header-only file, while eight-column reports write one row per `source_row`. The latest live eight-column replay produced 389 minimizer rows and 19 total clean outputs with zero parsing errors. Deployment and crawler schema validation remain pending. Related: [[entities/assets-etl-scripts]] and [[entities/pipeline-data-module]].

*Category: etl*

---
*Captured: 2026-09-28*

## Related

_Add links to related pages._
