---
type: source
title: "Observation: Removing cliPath proves child AWS CLI is required by current staging path"
tags:
  - nextflow
  - aws
  - batch
  - cliPath
  - s3
  - staging
  - taxprofiler
  - EFS
  - runtime
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-removing-clipath-proves-child-aws-cli-is-required-by-current
relevance: critical
observed_at: 2026-09-17T19:23:08.106Z
source_context: "Issue #379 no-cliPath taxprofiler canary"
---

# 🔴 Observation: Removing cliPath proves child AWS CLI is required by current staging path

A no-cliPath taxprofiler canary used the existing Nextflow job definition but omitted aws.batch.cliPath from a temporary config. This removed the previous container-start failures: Wave and FastQC child containers started instead of losing /usr/local entrypoints. The run then failed inside child staging commands with `bash: aws: command not found` and exit 127. Current nf-amazon AWS Batch staging therefore still requires a host-visible AWS CLI unless Fusion or another staging path is enabled. The test confirms a standalone host-AMI CLI at a non-conflicting path is a viable fallback, but the path must exist on every analysis Batch host and be supplied separately from the parent container's command-v aws path. No database mount was reached.

*Relevance: critical*
*Context: Issue #379 no-cliPath taxprofiler canary*
*Tags: nextflow aws batch cliPath s3 staging taxprofiler EFS runtime*

---
*Observed: 2026-09-17T19:23:08.106Z*
