---
type: source
title: "Observation: Actual deployed entrypoint smoke succeeds with work prefix and child Batch job"
tags:
  - aws
  - batch
  - nextflow
  - cli
  - path
  - workdir
  - deployed
  - smoke
  - success
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-actual-deployed-entrypoint-smoke-succeeds-with-work-prefix-a
relevance: critical
observed_at: 2026-09-14T18:19:32.496Z
source_context: Final deployed entrypoint smoke canary
---

# 🔴 Observation: Actual deployed entrypoint smoke succeeds with work prefix and child Batch job

Final actual-entrypoint canary `a11efe98-66f2-4f40-af00-881435123a6b` succeeded on Batch job definition 55 and image digest `sha256:df5f867edf959b0dd31874d726a2cbe9ed531dfebed4e03d453f371119a2af80`. The entrypoint logged `AWS_CLI_PATH=/usr/bin/aws`, used `-work-dir s3://nextflow-spot-batch-temp-a11efe98-66f2-4f40-af00-881435123a6b/work`, ran Nextflow 26.04.6, submitted child job `3e4df4c1-cbd8-48ae-b554-8c9168fc6b05`, and the child completed successfully. The temporary work bucket was cleaned up by the entrypoint. This validates both the dynamic AWS CLI path and the S3 work-prefix fix in the deployed runtime. The only warning was the expected irrelevant KRAKEN2 config selector warning for the smoke pipeline.

*Relevance: critical*
*Context: Final deployed entrypoint smoke canary*
*Tags: aws batch nextflow cli path workdir deployed smoke success*

---
*Observed: 2026-09-14T18:19:32.496Z*
