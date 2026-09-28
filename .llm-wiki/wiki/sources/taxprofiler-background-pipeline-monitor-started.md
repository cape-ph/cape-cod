---
type: source
title: Taxprofiler background pipeline monitor started
status: insight
category: operations
created: 2026-09-25
updated: 2026-09-25
slug: taxprofiler-background-pipeline-monitor-started
---

# Taxprofiler background pipeline monitor started

Started a persistent read-only monitor for the CAPE dev taxprofiler pipeline in us-east-2. It watches new `taxprofiler-output/<run>/` prefixes in the raw result bucket, prefers `pipeline_info/execution_report_*.html` as the workflow completion marker with Kraken2 report fallback, tracks Glue ETL job runs, checks core `kraken2_taxa` and `kraken2_summary` clean outputs, watches the seqauto result-clean Glue crawler, and confirms the two Athena catalog tables have partitions for the run. The monitor is background task `bg-10` with no expiry. It baselines the existing raw run and reports future run, ETL, crawler, failure, and Athena-readiness transitions. It performs no writes or deployments. Related: [[entities/assets-etl-scripts]] and [[concepts/testing-and-pulumi-preview-workflow]].

*Category: operations*

---
*Captured: 2026-09-25*

## Related

_Add links to related pages._
