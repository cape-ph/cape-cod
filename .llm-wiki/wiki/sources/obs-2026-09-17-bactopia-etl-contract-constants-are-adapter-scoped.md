---
type: source
title: "Observation: Bactopia ETL contract constants are adapter-scoped"
tags:
  - bactopia
  - etl
  - output-contract
  - naming
  - adapter
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-bactopia-etl-contract-constants-are-adapter-scoped
relevance: medium
observed_at: 2026-09-17T18:19:54.711Z
source_context: "Issue #379 ETL contract naming refinement"
---

# 🔍 Observation: Bactopia ETL contract constants are adapter-scoped

Updated assets/etl/etl_bactopia_results.py so contract-specific MLST and AMRFinderPlus schemas live on BactopiaOutputContractV1Adapter. Removed release-specific V4 constant names, renamed AMRFinderPlus filename constants to AMRFINDERPLUS_OBJ and AMRFINDERPLUS_LEGACY_OBJ, and updated tests to verify adapter-scoped schemas. Targeted ETL tests pass: 7 passed. The ETL changes remain uncommitted for review.

*Relevance: medium*
*Context: Issue #379 ETL contract naming refinement*
*Tags: bactopia etl output-contract naming adapter*

---
*Observed: 2026-09-17T18:19:54.711Z*
