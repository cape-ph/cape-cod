---
type: source
title: "Observation: Bactopia version migration includes in-repo ETL and reporting"
tags:
  - issue-379
  - bactopia
  - v4
  - etl
  - reporting
  - migration
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-bactopia-version-migration-includes-in-repo-etl-and-reportin
relevance: high
observed_at: 2026-09-23T16:33:15.294Z
source_context: Clarifying migration scope after separate taxprofiler architecture validation
---

# ⭐ Observation: Bactopia version migration includes in-repo ETL and reporting

Owner clarified that the Bactopia 4.1.0 migration scope includes CAPE Cod's in-repo ETL and reporting compatibility work. The external DAG repository remains separate, but assets/etl adapters, software metadata, report joins, output paths, semantic Kraken2 report handling, and historical v3 preservation belong in the version migration acceptance criteria. The current v4 ETL adapter and tests are part of this branch; remaining metadata/report validation should not be deferred merely because DAG orchestration is external.

*Relevance: high*
*Context: Clarifying migration scope after separate taxprofiler architecture validation*
*Tags: issue-379 bactopia v4 etl reporting migration*

---
*Observed: 2026-09-23T16:33:15.294Z*
