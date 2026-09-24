---
type: source
title: "Observation: Step 1 runtime contract separates parent and Batch host AWS CLI paths"
tags:
  - nextflow
  - aws
  - batch
  - cliPath
  - runtime
  - bactopia
  - taxprofiler
  - step1
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-step-1-runtime-contract-separates-parent-and-batch-host-aws-
relevance: high
observed_at: 2026-09-18T17:07:33.870Z
source_context: "Issue #379 step 1 runtime implementation"
---

# ⭐ Observation: Step 1 runtime contract separates parent and Batch host AWS CLI paths

Implemented the approved step 1 runtime change in the working tree. assets/containers/nextflow-kickstart/entrypoint.sh now validates the parent container AWS CLI separately and reads NEXTFLOW_AWS_BATCH_CLI_PATH for aws.batch.cliPath. Pulumi.cape-cod-dev.yaml passes /home/ec2-user/miniconda/bin/aws through the Nextflow Batch job definition environment. Added tests for the split contract. Validation passed: bash -n, Python compilation, 9 focused tests, git diff --check, LSP checks, and pulumi preview. The preview shows the expected kickstart image, Batch job-definition, and IAM cascade plus pre-existing ETL/DAP, Cognito, and identity-provider changes. The taxprofiler-specific resource override remains a separate profile/runtime-policy change; no commit or deployment occurred.

*Relevance: high*
*Context: Issue #379 step 1 runtime implementation*
*Tags: nextflow aws batch cliPath runtime bactopia taxprofiler step1*

---
*Observed: 2026-09-18T17:07:33.870Z*
