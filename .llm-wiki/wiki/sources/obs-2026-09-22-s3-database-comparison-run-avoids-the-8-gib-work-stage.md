---
type: source
title: "Observation: S3 database comparison run avoids the 8 GiB work stage"
tags:
  - issue-379
  - taxprofiler
  - s3
  - efs
  - comparison
  - staging
  - performance
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-s3-database-comparison-run-avoids-the-8-gib-work-stage
relevance: critical
observed_at: 2026-09-22T15:32:49.974Z
source_context: Direct EFS versus S3 database comparison
---

# 🔴 Observation: S3 database comparison run avoids the 8 GiB work stage

A direct nf-core/taxprofiler v2.0.1 comparison used the same 8.584 GB database as an uncompressed 17-object S3 directory, the same 2 vCPU / 9 GiB Kraken2 request, and the generation-3 queue without an EFS child volume. Parent job `c78b9314-7dbf-4cbf-bd0c-8c2f0359c9a6` succeeded in 373.338 seconds (6m13s); child `3ef90f66-f3fc-4f49-98fe-b9205484d486` waited 168.931 seconds and ran for 73.262 seconds. Its command used `--db database`, and it had only the host AWS CLI mount, not the EFS mount. The S3 work bucket contained no 8 GiB database stage, only about 2.4 MiB of workflow artifacts. The EFS-source baseline parent took 502.6 seconds (8m23s), child wait was 229.553 seconds, child runtime 118.725 seconds, and its work bucket contained the 8.584 GB `stage-*` database. S3 source was about 2m09 faster end-to-end in this single cold-start comparison and removed the EFS-to-S3 staging leg. Both produced the same valid synthetic Kraken2 report. The S3 canonical database prefix is `s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/taxprofiler-s3-db-comparison-20260922152323/`.

*Relevance: critical*
*Context: Direct EFS versus S3 database comparison*
*Tags: issue-379 taxprofiler s3 efs comparison staging performance*

---
*Observed: 2026-09-22T15:32:49.974Z*
