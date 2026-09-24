---
type: source
title: "Observation: Taxprofiler integration is the heavier migration lift"
tags:
  - bactopia
  - v4.1
  - taxprofiler
  - etl
  - database
  - design
  - nextflow
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-taxprofiler-integration-is-the-heavier-migration-lift
relevance: high
observed_at: 2026-09-17T17:43:23.960Z
source_context: "Issue #379 next-slice planning"
---

# ⭐ Observation: Taxprofiler integration is the heavier migration lift

Owner selected nf-core/taxprofiler for Kraken2, with a future goal of exposing the broader taxprofiler tool set while retaining a simple Kraken2-only route. The taxprofiler integration is the heavier lift than the parallel v4 ETL slice because the upstream workflow requires both a FASTQ samplesheet and a database sheet, supports multiple tools and long-read preprocessing, and needs a CAPE contract for tool selection, database staging, AWS Batch execution, canonical report output, and semantic parser compatibility. The database access strategy remains unresolved and can block the production-shaped integration. The parallel ETL slice can proceed independently using confirmed v4 MLST, AMRFinderPlus, assembler, Sourmash, and MASH fixtures and output-contract adapters.

*Relevance: high*
*Context: Issue #379 next-slice planning*
*Tags: bactopia v4.1 taxprofiler etl database design nextflow*

---
*Observed: 2026-09-17T17:43:23.960Z*
