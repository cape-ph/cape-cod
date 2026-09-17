---
type: source
title: "Observation: Bactopia v4 profiles and dynamic Batch submission wiring added"
tags:
  - bactopia
  - v4.1
  - nextflow
  - batch
  - dap
  - pulumi
  - migration
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-bactopia-v4-profiles-and-dynamic-batch-submission-wiring-add
relevance: high
observed_at: 2026-09-17T17:27:01.543Z
source_context: "Issue #379 next implementation slice"
---

# ⭐ Observation: Bactopia v4 profiles and dynamic Batch submission wiring added

Added versioned Bactopia v4.1 base and ONT DAP profiles at assets/analysis-pipelines/bactopia/bactopia-base-4.1.0.json and ont-bactopia-4.1.0.json. The v4 contract uses -profile docker, omits --aws_volumes, exposes configurable --skip_qc_plots with default true, and preserves the v3 fixtures. Batch submission now reads queue and job-definition names from deployment-provided Lambda environment variables; PrivateSwimlane resolves those values from Pulumi Batch resource outputs and passes them only to submit_dap_run through handler-scoped environment configuration. Targeted contract tests pass, and pulumi preview for cape-cod-dev showed two new DAP registry items, one submit Lambda update, and one pre-existing Cognito identity-provider update. No deployment or commit was performed.

*Relevance: high*
*Context: Issue #379 next implementation slice*
*Tags: bactopia v4.1 nextflow batch dap pulumi migration*

---
*Observed: 2026-09-17T17:27:01.543Z*
