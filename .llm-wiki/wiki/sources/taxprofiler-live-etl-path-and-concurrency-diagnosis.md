---
type: source
title: Taxprofiler live ETL path and concurrency diagnosis
status: insight
category: bugfix
created: 2026-09-25
updated: 2026-09-25
slug: taxprofiler-live-etl-path-and-concurrency-diagnosis
---

# Taxprofiler live ETL path and concurrency diagnosis

AWS CLI inspection of account 767397883306 in us-east-2 found two separate live behaviors. The deployed Glue job `ccd-dlh-T-seqauto-ETL-taxprofiler-results-6879b02` received 41 objects from sample `bactaxprof-01-dag-20260925T174037Z` and all 41 Glue runs eventually succeeded, but the deployed ETL logged `Taxprofiler ETL ignoring ... per configuration` because current nf-core/taxprofiler output uses `taxprofiler-output/<sample>/kraken2`, `multiqc`, and `pipeline_info` while the adapter only recognized an intermediate `output/` directory. The clean bucket had no taxprofiler outputs for `bactaxprof-01`, confirming silent data loss. The adapter now normalizes an optional `output/` segment and tests both layouts. Separately, the SQS mapping uses batch size 10 while the Glue job allows 5 concurrent runs; the Lambda logged 93 `ConcurrentRunsExceededException` retries during the burst. All messages eventually drained and the owner chose to keep retry backpressure unchanged. No deployment was run. Related: [[entities/assets-etl-scripts]] and [[concepts/testing-and-pulumi-preview-workflow]].

*Category: bugfix*

---
*Captured: 2026-09-25*

## Related

_Add links to related pages._
