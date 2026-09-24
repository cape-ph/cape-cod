---
type: source
title: Standalone v4 Kraken2 report compatible schema
status: insight
category: devops
created: 2026-09-16
updated: 2026-09-16
slug: standalone-v4-kraken2-report-compatible-schema
---

# Standalone v4 Kraken2 report compatible schema

The explicit EFS-backed standalone v4 Kraken2 canary persisted a report at `.../standalone-efs-canary-v4/v4-report.txt`. Compared with the v3.2 baseline report, both have 360 rows and the same taxid set, classification totals, and head/tail rows, but are not byte-identical. Differences include rank code `R2` versus `D` for Bacteria and ordering of low-count taxa. The current DAG's `parse_kraken2_report` parsed all 360 v4 rows and `render_kraken2_report_html` produced 147,823 bytes of HTML containing the sample and Bacteria. The report schema is compatible; migration documentation should mention rank/order differences and integration should avoid byte-level assumptions.

*Category: devops*

---
*Captured: 2026-09-16*

## Related

_Add links to related pages._
