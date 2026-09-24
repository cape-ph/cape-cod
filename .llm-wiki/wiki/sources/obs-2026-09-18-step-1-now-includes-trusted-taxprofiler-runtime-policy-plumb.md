---
type: source
title: "Observation: Step 1 now includes trusted taxprofiler runtime policy plumbing"
tags:
  - bactopia
  - taxprofiler
  - dap
  - runtime
  - policy
  - process
  - override
  - step1
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-step-1-now-includes-trusted-taxprofiler-runtime-policy-plumb
relevance: high
observed_at: 2026-09-18T17:22:39.784Z
source_context: "Issue #379 step 1 completion"
---

# ⭐ Observation: Step 1 now includes trusted taxprofiler runtime policy plumbing

Completed the remaining step 1 policy work in the working tree. Added assets/analysis-pipelines/bactopia/taxprofiler-kraken2-2.0.1.json with execution class taxonomic-profiling, semantic kraken2 process policy, and the 4 vCPU / 16 GiB / 4 hour initial override. submit_dap_run.py can resolve a trusted DAP profile by pipelineName/version and pass its structured process overrides to the parent as NEXTFLOW_PROCESS_OVERRIDES. The kickstart validates and renders only structured overrides into the generated Nextflow config. The host AWS CLI path split remains in place. Validation passed: bash -n, Python compilation, 19 focused tests, git diff --check, LSP diagnostics, and Pulumi preview. No commit or deployment was performed.

*Relevance: high*
*Context: Issue #379 step 1 completion*
*Tags: bactopia taxprofiler dap runtime policy process override step1*

---
*Observed: 2026-09-18T17:22:39.784Z*
