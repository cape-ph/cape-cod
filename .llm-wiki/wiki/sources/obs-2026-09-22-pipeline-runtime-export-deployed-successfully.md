---
type: source
title: "Observation: Pipeline runtime export deployed successfully"
tags:
  - pipeline-assets
  - pulumi
  - export
  - cape-cod-env
  - deployment
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-pipeline-runtime-export-deployed-successfully
relevance: high
observed_at: 2026-09-22T19:20:30.997Z
source_context: Post-deployment pipeline runtime export
---

# ⭐ Observation: Pipeline runtime export deployed successfully

The cape-cod-dev deployment completed without errors and materialized the `cape_pipeline_runtime_export` stack output. It exposes the meta-assets bucket `ccd-meta-assets-vbkt-s3-8b7134e`, prefixes `pipelines/`, `pipelines/manifests/`, and `pipelines/shared/databases/`, the DAP and workflow registry tables, Nextflow job definition revision 57, workflow and analysis queues, and execution routes. Both `general-analysis` and `taxonomic-profiling` resolve to the analysis queue; workflow orchestration resolves to the workflows queue. No asset was published yet.

*Relevance: high*
*Context: Post-deployment pipeline runtime export*
*Tags: pipeline-assets pulumi export cape-cod-env deployment*

---
*Observed: 2026-09-22T19:20:30.997Z*
