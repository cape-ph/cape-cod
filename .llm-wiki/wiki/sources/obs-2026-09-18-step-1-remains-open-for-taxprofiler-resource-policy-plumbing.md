---
type: source
title: "Observation: Step 1 remains open for taxprofiler resource-policy plumbing"
tags:
  - taxprofiler
  - resource
  - override
  - dap
  - runtime
  - step1
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-step-1-remains-open-for-taxprofiler-resource-policy-plumbing
relevance: high
observed_at: 2026-09-18T17:13:55.914Z
source_context: "Issue #379 step 1 scope correction"
---

# ⭐ Observation: Step 1 remains open for taxprofiler resource-policy plumbing

Correction: the step 1 implementation completed the parent/container versus Batch host AWS CLI path split, but the taxprofiler-specific Kraken2 resource override remains only in temporary canary configs. The override still needs to live in a versioned taxprofiler DAP/preset as structured policy and be carried through trusted profile selection into generated Nextflow config. Do not treat the shared host CLI fix alone as completion of step 1.

*Relevance: high*
*Context: Issue #379 step 1 scope correction*
*Tags: taxprofiler resource override dap runtime step1*

---
*Observed: 2026-09-18T17:13:55.914Z*
