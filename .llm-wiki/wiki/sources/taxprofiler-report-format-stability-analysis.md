---
type: source
title: Taxprofiler report format stability analysis
status: insight
category: testing
created: 2026-09-28
updated: 2026-09-28
slug: taxprofiler-report-format-stability-analysis
---

# Taxprofiler report format stability analysis

The supplied nf-core/taxprofiler v2.0.1 fixture and the latest live alias run use the same recorded versions, Kraken2 2.1.5, nf-core/taxprofiler `v2.0.1-g70ecc15`, and Nextflow 26.04.6, but their raw Kraken reports differ because the fixture has boolean `kraken2_save_minimizers=false` while the live params JSON has the string `"false"`. Upstream `conf/modules.config` appends `--report-minimizer-data` when that parameter is truthy, so Groovy truthiness enables the two minimizer fields for the live run. The fixture has 1,308 six-column rows; the live run has 389 eight-column rows. Input/database content also explains their different counts and taxa. The stable ETL contract now accepts uniform six- or eight-column reports, validates fields, rejects mixed/unknown widths, and normalizes both to the same Athena schema. A replay of 77 live objects produced 18 clean outputs with zero parsing errors. The external DAG should omit false boolean flags and pin `custom_config_version` instead of using `master`. Upstream sources: https://github.com/nf-core/taxprofiler/blob/2.0.1/conf/modules.config and https://github.com/nf-core/taxprofiler/blob/2.0.1/nextflow_schema.json. Related project knowledge: [[entities/assets-etl-scripts]] and [[concepts/testing-and-pulumi-preview-workflow]].

*Category: testing*

---
*Captured: 2026-09-28*

## Related

_Add links to related pages._
