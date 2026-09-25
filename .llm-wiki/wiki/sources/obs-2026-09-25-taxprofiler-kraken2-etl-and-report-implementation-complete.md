---
type: source
title: "Observation: Taxprofiler Kraken2 ETL and report implementation complete"
tags:
  - taxprofiler
  - kraken2
  - etl
  - glue
  - athena
  - report
  - pulumi
status: observation
created: 2026-09-25
updated: 2026-09-25
slug: obs-2026-09-25-taxprofiler-kraken2-etl-and-report-implementation-complete
relevance: critical
observed_at: 2026-09-25T14:34:59.487Z
source_context: Completed approved taxprofiler Kraken2 ETL and report implementation
---

# 🔴 Observation: Taxprofiler Kraken2 ETL and report implementation complete

Implemented taxprofiler Kraken2 ingestion and report wiring in cape-cod. New assets/etl/etl_taxprofiler_results.py parses the 1,308-row Kraken report plus selected MultiQC, params, versions, trace, and execution metadata into 18 collision-free clean outputs in local replay. Added assets/report/taxprofiler-kraken2/data_function.py and template.html.j2, report ID taxprofiler-kraken2, seqauto ETL registration, and deferred report-role S3/Athena data access wiring. Read-only AWS inspection covered 73 live S3 objects, the seqauto Glue database ccd-dlh-t-seqauto-catalog_mczhqmdk, and the result-clean crawler. Focused tests pass 15; full suite has 118 passes and two known pre-existing Pulumi mock failures. pulumi preview --diff -s cape-cod-dev succeeded with 14 creates, 7 updates, and 3 unrelated deletes; no deploy was run. The deletes are local-dev Cognito/user-attribute drift and require owner review before deployment.

*Relevance: critical*
*Context: Completed approved taxprofiler Kraken2 ETL and report implementation*
*Tags: taxprofiler kraken2 etl glue athena report pulumi*

---
*Observed: 2026-09-25T14:34:59.487Z*
