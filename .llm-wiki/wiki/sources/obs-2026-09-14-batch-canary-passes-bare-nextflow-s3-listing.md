---
type: source
title: "Observation: Batch canary passes bare Nextflow S3 listing"
tags:
  - aws
  - batch
  - nextflow
  - s3
  - kraken2
  - diagnosis
  - bactopia
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-batch-canary-passes-bare-nextflow-s3-listing
relevance: high
observed_at: 2026-09-14T16:20:16.041Z
source_context: Corrected Batch S3-listing canary after initial harness error
---

# ⭐ Observation: Batch canary passes bare Nextflow S3 listing

The corrected diagnostic Batch job `68570a92-8738-4eb5-afdc-9011cb8572f5` succeeded on the same workflow Batch host `i-0f3dc82a65ab8f8c7` and image digest as the hung job. In the container, AWS CLI `list-objects-v2` against `pipeline-output/` returned 24 immediate prefixes, and Nextflow 25.10.4 with nf-amazon 3.4.4 completed a bare `file('s3://.../pipeline-output/').eachFile` and listed `kraken-debug-0`. This rules out a generic Batch S3 permission/network failure and a bare Nextflow S3 eachFile failure. The canary also confirmed `/usr/bin/aws` is present but `/home/ec2-user/miniconda/bin/aws` is absent. Bactopia's remaining path performs `item.isDirectory()`, `_is_sample_dir()` with `file("${dir}/${sample}").exists()`, and `_collect_inputs()` with multiple S3-backed `.exists()` checks, so the next diagnostic should reproduce those per-entry metadata checks without submitting child jobs.

*Relevance: high*
*Context: Corrected Batch S3-listing canary after initial harness error*
*Tags: aws batch nextflow s3 kraken2 diagnosis bactopia*

---
*Observed: 2026-09-14T16:20:16.041Z*
