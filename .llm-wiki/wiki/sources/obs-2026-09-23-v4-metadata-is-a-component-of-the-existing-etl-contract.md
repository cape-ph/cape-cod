---
type: source
title: "Observation: V4 metadata is a component of the existing ETL contract"
tags:
  - issue-379
  - bactopia
  - v4
  - etl
  - output-contract
  - metadata
  - report
  - joins
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-v4-metadata-is-a-component-of-the-existing-etl-contract
relevance: high
observed_at: 2026-09-23T17:46:38.187Z
source_context: Clarifying the next ETL implementation step
---

# ⭐ Observation: V4 metadata is a component of the existing ETL contract

Code review clarified that the next metadata step is not a new unrelated contract. assets/etl/etl_bactopia_results.py already defines BactopiaOutputContractV1Adapter for v4 MLST and AMRFinderPlus results, while etl_bactopia_samples.py defines BactopiaOutputContractV1SampleAdapter for v4 sample outputs. The remaining gap is the run-metadata component: current SOFTWARE_VERSION_OBJ handling still expects legacy software_versions.yml, while the report joins require crawlable input_file, bactopia_run, sample/run, version, and date data. Complete the v4 output contract with a metadata component/adapter and fixtures, then validate the report path end to end.

*Relevance: high*
*Context: Clarifying the next ETL implementation step*
*Tags: issue-379 bactopia v4 etl output-contract metadata report joins*

---
*Observed: 2026-09-23T17:46:38.187Z*
