---
type: source
title: "Observation: Bactopia v4 ETL contract slice validated"
tags:
  - bactopia
  - v4.1
  - etl
  - output-contract
  - mlst
  - amrfinderplus
  - samples
  - taxprofiler
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-bactopia-v4-etl-contract-slice-validated
relevance: high
observed_at: 2026-09-17T17:52:49.129Z
source_context: "Issue #379 parallel ETL implementation slice"
---

# ⭐ Observation: Bactopia v4 ETL contract slice validated

Implemented the parallel Bactopia v4 ETL slice without changing run metadata joins or Pulumi trigger prefixes. etl_bactopia_results.py now has a BactopiaOutputContractV1Adapter that validates the headered six-column MLST contract, preserves ALLELES as one field, and validates AMRFinderPlus report-query columns. etl_bactopia_samples.py now uses a named v4 sample adapter and validates delimited row shapes for assembler, MASH, and Sourmash outputs. Added five checked-in v4 fixtures and Glue-style fake-EtlJob contract tests. Targeted v4 profile plus ETL tests pass: 14 passed. Pulumi preview shows two new DAP registry items and updates for the ETL script assets and prior un-deployed slice; no deployment was run. Run metadata remains intentionally deferred pending the CAPE-owned sidecar or registry design.

*Relevance: high*
*Context: Issue #379 parallel ETL implementation slice*
*Tags: bactopia v4.1 etl output-contract mlst amrfinderplus samples taxprofiler*

---
*Observed: 2026-09-17T17:52:49.129Z*
