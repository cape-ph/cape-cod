---
type: source
title: "Observation: Tactical EFS bridge versus generic Batch capability model remains open"
tags:
  - bactopia
  - taxprofiler
  - efs
  - aws
  - batch
  - architecture
  - decision
  - deferred
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-tactical-efs-bridge-versus-generic-batch-capability-model-re
relevance: high
observed_at: 2026-09-18T16:14:46.331Z
source_context: "Issue #379 scope discussion"
---

# ⭐ Observation: Tactical EFS bridge versus generic Batch capability model remains open

The generic capability-aware Batch volume architecture is a substantial long-term platform effort. For the immediate Bactopia/taxprofiler migration, a smaller tactical bridge may be acceptable: prepare a dedicated or explicitly EFS-capable analysis host pool for the current shared Kraken2 EFS database, keep the logical/runtime boundary clear, and track generic N-volume capability scheduling as follow-up. Owner has not selected between accepting that tactical special case and pausing until the generic model is designed. No implementation decision or infrastructure change was made.

*Relevance: high*
*Context: Issue #379 scope discussion*
*Tags: bactopia taxprofiler efs aws batch architecture decision deferred*

---
*Observed: 2026-09-18T16:14:46.331Z*
