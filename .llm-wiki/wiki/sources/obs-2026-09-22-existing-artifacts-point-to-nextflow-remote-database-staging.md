---
type: source
title: "Observation: Existing artifacts point to Nextflow remote database staging"
tags:
  - issue-379
  - nextflow
  - aws-batch
  - efs
  - database
  - staging
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-existing-artifacts-point-to-nextflow-remote-database-staging
relevance: high
observed_at: 2026-09-22T14:17:40.653Z
source_context: Read-only inspection of successful taxprofiler work bucket
---

# ⭐ Observation: Existing artifacts point to Nextflow remote database staging

Read-only inspection of the successful 2-vCPU / 9-GiB taxprofiler run found 17 database objects totaling 8,584,309,607 bytes under a separate `work/stage-b3bf24c3-5945-4008-b1b4-1533c29c8a24/.../kraken2/` prefix. The Kraken2 task work prefix contains no database files; `.command.sh` only invokes `kraken2 --db kraken2`, and `.command.run` contains no S3 copy or EFS path reference. The child did have the EFS host mount, but these artifacts strongly indicate Nextflow/AWS Batch remote staging occurred before task execution. A minimal executor-only path probe with the same S3 work directory, EFS volume, and symlink staging is warranted to distinguish executor staging from taxprofiler database handling.

*Relevance: high*
*Context: Read-only inspection of successful taxprofiler work bucket*
*Tags: issue-379 nextflow aws-batch efs database staging*

---
*Observed: 2026-09-22T14:17:40.653Z*
