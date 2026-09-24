---
type: source
title: "Observation: Shared Nextflow runtime config is preferred"
tags:
  - nextflow
  - config
  - dap
  - runtime
  - aws
  - batch
  - design
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-shared-nextflow-runtime-config-is-preferred
relevance: high
observed_at: 2026-09-17T16:22:52.909Z
source_context: Owner feedback on Bactopia v4.1 implementation design
---

# ⭐ Observation: Shared Nextflow runtime config is preferred

Owner clarified that CAPE should first attempt one shared generated Nextflow runtime config for all Nextflow DAPs. The shared config should own AWS Batch execution settings such as executor, dynamically resolved queue/region/CLI path, and common work/cache behavior. Pipeline profiles should own pipeline-specific options. A pipeline-specific Nextflow override is a deviation requiring design iteration and owner approval. The implementation design and new-session handoff now record this shared-config-first approach.

*Relevance: high*
*Context: Owner feedback on Bactopia v4.1 implementation design*
*Tags: nextflow config dap runtime aws batch design*

---
*Observed: 2026-09-17T16:22:52.909Z*
