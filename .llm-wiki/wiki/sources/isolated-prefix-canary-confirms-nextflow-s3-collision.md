---
type: source
title: Isolated prefix canary confirms Nextflow S3 collision
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: isolated-prefix-canary-confirms-nextflow-s3-collision
---

# Isolated prefix canary confirms Nextflow S3 collision

The corrected isolated-prefix canary `c47781a4-2dfc-445d-9baf-684efbba830a` succeeded on the same AWS Batch image, host, IAM role, and network as the failing job. The scratch root `s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/kraken2/prefix-canary-20260914165156/pipeline-output` contained only `kraken-debug-0` with the QC FASTQ and NanoPlot report. Nextflow 25.10.4/nf-amazon 3.4.4 completed `isDirectory()`, sample-directory existence, QC FASTQ existence, QC report existence, and the expected missing paired-read checks.

This is a causal A/B result. The full `pipeline-output/` root hangs at `isDirectory()` for unrelated `micah-test` while `micah-test-2`, `micah-test-3`, and `micah-test-4` exist as sibling prefixes. The isolated root completes. Official Nextflow issue #6999 has the same title and environment, and issue #7224 explains that `S3ObjectSummaryLookup` strips the trailing slash and lists the bare prefix, over-listing sibling prefixes. PR #6851 adds bounded lookup logic with a `key + "/"` fallback, but the issue discussion says it was not backported to 25.10.x. The scratch objects were intentionally left for explicit cleanup approval; no original S3 objects were changed.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
