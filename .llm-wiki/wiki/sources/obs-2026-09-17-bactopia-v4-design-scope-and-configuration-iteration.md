---
type: source
title: "Observation: Bactopia v4 design scope and configuration iteration"
tags:
  - bactopia
  - v4
  - design
  - nextflow
  - config
  - etl
  - adapters
  - scope
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-bactopia-v4-design-scope-and-configuration-iteration
relevance: high
observed_at: 2026-09-17T15:23:07.834Z
source_context: Owner review of Bactopia 4.1 CAPE Cod implementation design
---

# ⭐ Observation: Bactopia v4 design scope and configuration iteration

Owner review revised the Bactopia v4 implementation design. Current implementation scope is cape-cod only; Airflow DAG, frontend, MWAA, and new profiler-repository work are external handoffs unless explicitly expanded. AWS resource IDs must be resolved from deployment/runtime context or a future registry, never hard-coded in DAP profiles. The design now separates pipeline configuration from a generated Nextflow runtime adapter, assumes a constant supported Nextflow version for now, defaults v4 QC to skip plots while exposing the flag for opt-in full QC, and uses output-contract adapters rather than Bactopia-version-named ETL classes. Report metadata should come from a CAPE-owned run sidecar/metadata table or an iterative registry design, not a new file added to Bactopia output by default. Design document: .llm-wiki/wiki/analyses/bactopia-41-cape-cod-implementation-design.md.

*Relevance: high*
*Context: Owner review of Bactopia 4.1 CAPE Cod implementation design*
*Tags: bactopia v4 design nextflow config etl adapters scope*

---
*Observed: 2026-09-17T15:23:07.834Z*
