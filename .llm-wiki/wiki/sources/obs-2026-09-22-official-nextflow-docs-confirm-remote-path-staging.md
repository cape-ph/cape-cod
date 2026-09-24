---
type: source
title: "Observation: Official Nextflow docs confirm remote path staging"
tags:
  - issue-379
  - nextflow
  - documentation
  - aws-batch
  - s3
  - efs
  - staging
  - proof
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-official-nextflow-docs-confirm-remote-path-staging
relevance: critical
observed_at: 2026-09-22T15:29:07.783Z
source_context: Official Nextflow documentation review
---

# 🔴 Observation: Official Nextflow docs confirm remote path staging

Official Nextflow documentation provides the direct justification for the EFS-to-S3 staging behavior. `docs/working-with-files.mdx` says Nextflow automatically stages files based on process inputs and outputs; when a process input file resides on a different filesystem than the work directory, Nextflow copies it into the work directory. It names the resulting `stage-<session-id>/<hash>/<filename>` layout and notes that large remote staging can bottleneck. The same section says a `val` input bypasses built-in remote staging, while Fusion can access remote files directly with object-storage work directories. `docs/aws.mdx` says AWS Batch uses S3 for its work directory and uses the AWS CLI to stage input and output files between S3 and task containers. In CAPE, the database is a Nextflow `path db` input, the parent sees it through EFS, and workDir is S3, so the documented condition applies. This is conditional on different filesystems and the S3 AWS Batch workDir, not a universal rule for every Nextflow deployment.

*Relevance: critical*
*Context: Official Nextflow documentation review*
*Tags: issue-379 nextflow documentation aws-batch s3 efs staging proof*

---
*Observed: 2026-09-22T15:29:07.783Z*
