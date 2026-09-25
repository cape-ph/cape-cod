---
type: source
title: Taxprofiler Kraken2 report implementation plan
status: insight
category: architecture
created: 2026-09-25
updated: 2026-09-25
slug: taxprofiler-kraken2-report-plan
---

# Taxprofiler Kraken2 report implementation plan

The implementation plan for the supplied taxprofiler output is recorded in `PLAN.md` and `.slim/deepwork/taxprofiler-kraken2-report.md`. The target is a dedicated `etl_taxprofiler_results.py`, stable Athena tables for taxa/summary and selected versions, params, trace, and MultiQC data, plus `assets/report/taxprofiler-kraken2/` with an Athena data function and a legacy-compatible Jinja template. The primary Kraken report is compatible with the legacy six-field parser, but it is produced before MultiQC; report readiness should be separated from full-workflow completion. The generic `/report/create` path remains the delivery target. Owner approval is still required for the split readiness contract, exact cleanup boundary, and final plan approval.

*Category: architecture*

---
*Captured: 2026-09-25*

## Related

_Add links to related pages._
