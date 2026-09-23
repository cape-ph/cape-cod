---
type: source
title: "Observation: Current database path has two-stage EFS-to-S3-to-local flow"
tags:
  - issue-379
  - efs
  - s3
  - nextflow
  - staging
  - dataflow
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-current-database-path-has-two-stage-efs-to-s3-to-local-flow
relevance: high
observed_at: 2026-09-22T15:17:56.309Z
source_context: Clarification of database movement for cost comparison
---

# ⭐ Observation: Current database path has two-stage EFS-to-S3-to-local flow

Clarification: in the current EFS-backed AWS Batch setup, the parent Nextflow container sees `/mnt/nextflow_shared_data/kraken2`, Nextflow uploads the `path db` directory into an S3 `work/stage-*` prefix, and the dynamic child materializes that staged directory into `/tmp/nxf.../kraken2` on its local overlay filesystem. The child EFS mount is present but is not the database path used by Kraken2. With a canonical S3 database and the same current executor, the expected minimum flow is canonical S3 -> S3 work-stage prefix -> local child copy; whether Nextflow performs the S3-to-stage leg server-side or through the parent must be measured. A comparison should use an uncompressed S3 directory with the same database objects, not the small mock archive, to keep the staging paths comparable.

*Relevance: high*
*Context: Clarification of database movement for cost comparison*
*Tags: issue-379 efs s3 nextflow staging dataflow*

---
*Observed: 2026-09-22T15:17:56.309Z*
