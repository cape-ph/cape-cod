---
type: source
title: "Observation: Minimal EFS path probe proves Nextflow copies database input"
tags:
  - issue-379
  - nextflow
  - aws-batch
  - efs
  - path-staging
  - taxprofiler
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-minimal-efs-path-probe-proves-nextflow-copies-database-input
relevance: critical
observed_at: 2026-09-22T14:40:14.625Z
source_context: Corrected minimal EFS path-staging probe
---

# 🔴 Observation: Minimal EFS path probe proves Nextflow copies database input

The corrected minimal AWS Batch Nextflow probe succeeded. It used the EFS host mount, an S3 work directory, global `stageInMode = 'symlink'`, and a direct path input `/mnt/nextflow_shared_data/kraken2`. The probe reproduced the 8 GiB `work/stage-*` prefix before the child ran. Inside the child, `db_arg=kraken2`, `db_real=/tmp/nxf.cZc3mgpTZY/kraken2`, `db_device=47`, while the EFS hash file had `db_hash_device=52`; `/mnt/nextflow_shared_data` was mounted as NFSv4. The database path was therefore copied into task-local overlay storage rather than symlinked to EFS. This isolates the behavior to Nextflow AWS Batch path staging with an S3 work directory. Taxprofiler itself passes uncompressed `db_path` through to a Kraken2 module declared with `path db`, and has no CLI switch to disable this. Avoiding the copy requires a design change such as a value-based stable EFS path, shared filesystem work directory, or filesystem-aware executor.

*Relevance: critical*
*Context: Corrected minimal EFS path-staging probe*
*Tags: issue-379 nextflow aws-batch efs path-staging taxprofiler*

---
*Observed: 2026-09-22T14:40:14.625Z*
