---
type: source
title: "Observation: Diagnosis proposal for taxprofiler 8 GiB database staging"
tags:
  - issue-379
  - nextflow
  - aws-batch
  - efs
  - taxprofiler
  - staging
  - diagnosis
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-diagnosis-proposal-for-taxprofiler-8-gib-database-staging
relevance: high
observed_at: 2026-09-22T14:14:18.506Z
source_context: Proposal after successful 2-vCPU 9-GiB direct run
---

# ⭐ Observation: Diagnosis proposal for taxprofiler 8 GiB database staging

The successful direct taxprofiler run proves the generation-3 child mounted EFS and completed Kraken2 at 2 vCPUs and 9 GiB, but its temporary S3 work bucket still contains about 8 GiB of database-stage artifacts. Diagnose before changing production configuration. First inspect the preserved work bucket's `.command.run`, `.command.env`, `.command.trace`, task log, Nextflow execution trace, and stage-prefix object metadata. The Kraken2 command used `--db kraken2`; add a diagnostic retry with `readlink -f kraken2`, `findmnt -T /mnt/nextflow_shared_data/kraken2`, and file device/inode checks to determine whether the task reads the EFS mount or a copied work-directory database. Next run a minimal AWS Batch Nextflow path-input probe with the same S3 workDir, EFS host volume, and `stageInMode = 'symlink'` but no taxprofiler code. If the minimal probe creates the 8 GiB stage prefix, the AWS Batch/S3 executor is copying a cross-filesystem path and the staging is executor behavior. If only taxprofiler creates it, inspect its database-sheet/path handling or an unmatched upstream process selector. Nextflow documentation distinguishes `stageInMode` task-directory staging from remote-file staging and treats `aws.batch.volumes` as a separate mount configuration. Do not change the shared DAP/API or Pulumi contract until this split is known.

*Relevance: high*
*Context: Proposal after successful 2-vCPU 9-GiB direct run*
*Tags: issue-379 nextflow aws-batch efs taxprofiler staging diagnosis*

---
*Observed: 2026-09-22T14:14:18.506Z*
