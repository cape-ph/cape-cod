---
type: source
title: "Observation: Direct taxprofiler run blocked by m5.xlarge memory ceiling"
tags:
  - issue-379
  - taxprofiler
  - aws-batch
  - kraken2
  - resources
  - efs
  - nextflow
status: observation
created: 2026-09-21
updated: 2026-09-21
slug: obs-2026-09-21-direct-taxprofiler-run-blocked-by-m5-xlarge-memory-ceiling
relevance: critical
observed_at: 2026-09-21T20:34:08.269Z
source_context: Stopped direct taxprofiler test
---

# 🔴 Observation: Direct taxprofiler run blocked by m5.xlarge memory ceiling

The direct generation-3 nf-core/taxprofiler v2.0.1 test was submitted with 4 vCPU and 16 GiB Kraken2 resources and then stopped at the user's request. AWS Batch marked the Kraken2 child RUNNABLE with `MISCONFIGURATION:JOB_RESOURCE_REQUIREMENT` because an m5.xlarge provides 4 vCPU and 16,384 MiB nominal memory, while ECS/Batch reserves part of that memory. The parent job was terminated and the child was canceled; no Kraken2 classification completed. The run did stage the EFS database into the temporary Nextflow work bucket, which contained about 8 GiB. The custom direct config omitted the `stageInMode = 'symlink'` rule used by the normal kickstart config, so tomorrow's retry must preserve both the explicit EFS host volume mapping and Kraken2 symlink staging. Temporary bucket `s3://nextflow-spot-batch-temp-acebda2c-33ac-4871-9270-862e710c263f/` was intentionally preserved for tomorrow; result metadata remains under `s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/taxprofiler-direct-g3-20260921192441/`.

*Relevance: critical*
*Context: Stopped direct taxprofiler test*
*Tags: issue-379 taxprofiler aws-batch kraken2 resources efs nextflow*

---
*Observed: 2026-09-21T20:34:08.269Z*
