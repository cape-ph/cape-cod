---
type: source
title: "Observation: Actual entrypoint smoke hits S3 work-directory root issue"
tags:
  - nextflow
  - s3
  - workdir
  - batch
  - entrypoint
  - cli
  - path
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-actual-entrypoint-smoke-hits-s3-work-directory-root-issue
relevance: high
observed_at: 2026-09-14T18:06:48.973Z
source_context: Actual entrypoint CLI smoke canary
---

# ⭐ Observation: Actual entrypoint smoke hits S3 work-directory root issue

The actual entrypoint canary on Batch job definition 54 correctly logged `AWS_CLI_PATH=/usr/bin/aws` and generated Nextflow 26.04.6 config, but failed before child submission with `Creating a bucket is not supported`. The entrypoint creates a temporary S3 bucket and passes the bucket root as `-work-dir s3://nextflow-spot-batch-temp-<jobid>`. Nextflow 26.04.6 rejects this root-directory operation; a prior explicit-config canary using an existing bucket subprefix successfully submitted child job `12dba23c-0177-4ccf-89f5-faf6106fc9f6` with `/usr/bin/aws`. The next proposed entrypoint change is to use a work subprefix such as `s3://${BUCKET_TEMP_NAME}/work`, then rebuild and rerun the actual entrypoint smoke. No source change has been made for this new work-directory issue.

*Relevance: high*
*Context: Actual entrypoint CLI smoke canary*
*Tags: nextflow s3 workdir batch entrypoint cli path*

---
*Observed: 2026-09-14T18:06:48.973Z*
