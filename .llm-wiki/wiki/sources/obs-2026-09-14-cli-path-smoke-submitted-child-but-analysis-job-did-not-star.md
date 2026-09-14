---
type: source
title: "Observation: CLI path smoke submitted child but analysis job did not start"
tags:
  - aws
  - batch
  - nextflow
  - cli
  - path
  - smoke
  - test
  - deployment
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-cli-path-smoke-submitted-child-but-analysis-job-did-not-star
relevance: high
observed_at: 2026-09-14T18:00:57.841Z
source_context: CLI path canary and entrypoint fix
---

# ⭐ Observation: CLI path smoke submitted child but analysis job did not start

The deployed-image CLI-path smoke canary `92c96baa-69c3-4f32-bca1-fdf08af89fec` ran Nextflow 26.04.6 with `aws.batch.cliPath=/usr/bin/aws`. Nextflow created child Batch job `12dba23c-0177-4ccf-89f5-faf6106fc9f6` named `CLI_SMOKE_cli-path-smoke`, proving the configured CLI path was accepted and used for submission. The child had no `startedAt` and was later marked `Job killed by NF` when the parent timed out after 150 seconds, so child scheduling/startup remains a separate issue. The entrypoint was then updated to derive `AWS_CLI_PATH=$(command -v aws)` and write that path into `/nextflow.config`; `bash -n` and `git diff --check` pass. Pulumi preview now shows the expected image, Batch job-definition, and IAM updates pending.

*Relevance: high*
*Context: CLI path canary and entrypoint fix*
*Tags: aws batch nextflow cli path smoke test deployment*

---
*Observed: 2026-09-14T18:00:57.841Z*
