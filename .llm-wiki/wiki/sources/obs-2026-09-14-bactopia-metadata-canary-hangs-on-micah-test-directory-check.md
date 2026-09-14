---
type: source
title: "Observation: Bactopia metadata canary hangs on micah-test directory check"
tags:
  - aws
  - batch
  - nextflow
  - s3
  - bactopia
  - kraken2
  - root-cause
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-bactopia-metadata-canary-hangs-on-micah-test-directory-check
relevance: critical
observed_at: 2026-09-14T16:43:56.954Z
source_context: Bactopia per-entry S3 metadata canary
---

# 🔴 Observation: Bactopia metadata canary hangs on micah-test directory check

The Bactopia-style Batch canary `7beb259c-c82a-4b32-920b-f599f2ec721f` ran on the same current image and Batch host, then was hard-stopped after 180 seconds. It completed `isDirectory()` and `getName()` for all preceding top-level prefixes, including the target `kraken-debug-0`; the target sample directory, QC FASTQ, and QC report `.exists()` checks all returned true, while paired-read checks returned false as expected. The canary then logged `BEFORE_IS_DIRECTORY` for `s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/pipeline-output/micah-test` and never logged the corresponding `AFTER_IS_DIRECTORY`. AWS CLI inspection shows no object at the exact `micah-test` or `micah-test/` keys, but 117 child objects under `micah-test/`; the root also has sibling prefixes `micah-test-2/`, `micah-test-3/`, and `micah-test-4/`. Leading diagnosis is a Nextflow 25.10.4/nf-amazon S3 `isDirectory()` edge case when a directory name is a prefix of sibling directory names. Bactopia checks every top-level item before applying its include filter, so the unrelated `micah-test` prefix blocks processing of the included `kraken-debug-0` sample.

*Relevance: critical*
*Context: Bactopia per-entry S3 metadata canary*
*Tags: aws batch nextflow s3 bactopia kraken2 root-cause*

---
*Observed: 2026-09-14T16:43:56.954Z*
