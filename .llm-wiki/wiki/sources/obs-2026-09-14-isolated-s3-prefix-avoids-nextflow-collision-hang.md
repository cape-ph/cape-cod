---
type: source
title: "Observation: Isolated S3 prefix avoids Nextflow collision hang"
tags:
  - aws
  - batch
  - nextflow
  - s3
  - bactopia
  - kraken2
  - confirmed
  - root-cause
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-isolated-s3-prefix-avoids-nextflow-collision-hang
relevance: critical
observed_at: 2026-09-14T16:54:13.589Z
source_context: Isolated S3 prefix canary and Nextflow issue correlation
---

# 🔴 Observation: Isolated S3 prefix avoids Nextflow collision hang

The corrected isolated-prefix Batch canary `c47781a4-2dfc-445d-9baf-684efbba830a` succeeded on the same current image and Batch host. It used scratch prefix `batch_job_scratch/kraken2/prefix-canary-20260914165156`, containing only the `kraken-debug-0` sample directory with the QC FASTQ and NanoPlot report. AWS CLI found one top-level prefix. Nextflow 25.10.4/nf-amazon 3.4.4 completed `isDirectory()`, sample-directory `.exists()`, QC file `.exists()` checks, and logged `NEXTFLOW_ISOLATED_PREFIX_COMPLETED`. This is the causal A/B result: the original root hangs at `micah-test`, while an otherwise equivalent isolated root without the colliding sibling prefixes succeeds. Official Nextflow issue #6999 documents the same S3 prefix-collision hang in Nextflow 25.10.4, and issue #7224 describes the bare-prefix listing behavior; fix PR #6851 is merged to master but not backported to 25.10.x per the issue discussion.

*Relevance: critical*
*Context: Isolated S3 prefix canary and Nextflow issue correlation*
*Tags: aws batch nextflow s3 bactopia kraken2 confirmed root-cause*

---
*Observed: 2026-09-14T16:54:13.589Z*
