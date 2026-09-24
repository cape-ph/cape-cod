---
type: source
title: "Observation: Generation 3 dynamic EFS sentinel passed"
tags:
  - issue-379
  - generation3
  - efs
  - sentinel
  - aws
  - batch
  - nextflow
  - taxprofiler
status: observation
created: 2026-09-21
updated: 2026-09-21
slug: obs-2026-09-21-generation-3-dynamic-efs-sentinel-passed
relevance: critical
observed_at: 2026-09-21T19:14:54.640Z
source_context: Post-deployment dynamic EFS validation
---

# 🔴 Observation: Generation 3 dynamic EFS sentinel passed

Generation 3 CAPE Cod deployment and the dynamic EFS sentinel completed successfully. The deployed compute environment `ccd-pvsl-taxonomic-profiling-g3-btch-cmpt-env` and queue `ccd-pvsl-taxonomic-profiling-g3-btch-jobq-a8f4880` were ENABLED and VALID. Parent Nextflow job `ede4027f-612f-4fae-a584-30c8e34e0eb1` succeeded, and child job `3ce3e87c-b457-4511-a2a5-254135cccdb4` succeeded with exit code 0. The actual Batch child container showed host-path volumes for `/home/ec2-user/miniconda` and `/mnt/nextflow_shared_data`; the sentinel verified `hash.k2d`, `opts.k2d`, and `taxo.k2d` under `/mnt/nextflow_shared_data/kraken2`. The corrected AMI includes the host AWS CLI profile. Temporary pipeline/work buckets were removed. The test used an explicit sentinel Nextflow config for the host volume mapping and did not run real taxprofiler execution.

*Relevance: critical*
*Context: Post-deployment dynamic EFS validation*
*Tags: issue-379 generation3 efs sentinel aws batch nextflow taxprofiler*

---
*Observed: 2026-09-21T19:14:54.640Z*
