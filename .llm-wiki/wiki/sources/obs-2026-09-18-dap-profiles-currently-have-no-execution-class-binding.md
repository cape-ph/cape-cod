---
type: source
title: "Observation: DAP profiles currently have no execution-class binding"
tags:
  - dap
  - execution-class
  - batch
  - compute
  - pipeline
  - registry
  - architecture
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-dap-profiles-currently-have-no-execution-class-binding
relevance: high
observed_at: 2026-09-18T16:26:36.735Z
source_context: "Issue #379 generic execution architecture discussion"
---

# ⭐ Observation: DAP profiles currently have no execution-class binding

CAPE currently has no configured execution-class concept tying DAP JSON fixtures to Batch compute environments. Pulumi.cape-cod-dev.yaml defines infrastructure under compute.environments.batch, while DAPRegistry globs assets/analysis-pipelines/*.json and stores profiles independently. submit_dap_run.py currently accepts pipeline project/version/options and resolves only the fixed workflow/analysis Batch resources; it does not resolve a DAP profile or execution class. A future contract should add a logical execution class or capability requirement to each DAP profile and a sibling compute.execution_classes mapping in the same Pulumi private swimlane config. The mapping should refer to logical Batch environment names and capabilities, while runtime outputs resolve physical queues, job definitions, and volume behavior. No code change was made.

*Relevance: high*
*Context: Issue #379 generic execution architecture discussion*
*Tags: dap execution-class batch compute pipeline registry architecture*

---
*Observed: 2026-09-18T16:26:36.735Z*
