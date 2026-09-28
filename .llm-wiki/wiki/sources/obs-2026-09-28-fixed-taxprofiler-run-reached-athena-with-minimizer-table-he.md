---
type: source
title: "Observation: Fixed taxprofiler run reached Athena with minimizer table header-only"
tags:
  - taxprofiler
  - deployment
  - etl
  - crawler
  - athena
  - minimizers
status: observation
created: 2026-09-28
updated: 2026-09-28
slug: obs-2026-09-28-fixed-taxprofiler-run-reached-athena-with-minimizer-table-he
relevance: high
observed_at: 2026-09-28T14:07:03.503Z
source_context: Live monitor completed the deployed fixed taxprofiler run
---

# ⭐ Observation: Fixed taxprofiler run reached Athena with minimizer table header-only

Live monitor observed `bactaxprof-01-fixed-20260928T134936Z` complete: 23 Glue ETL runs terminal, core clean outputs present, result-clean crawler completed, and both Kraken2 Athena tables have the run partition. The deployed ETL asset includes minimizer capture. This run's params contain boolean `kraken2_save_minimizers: false` and its 389-row raw report is six-column, so the minimizer clean object is intentionally header-only. Glue created `result_kraken2_minimizers` with the expected partitions but no data columns because no minimizer rows existed; an enabled eight-column run is still needed to validate crawler type inference for that table.

*Relevance: high*
*Context: Live monitor completed the deployed fixed taxprofiler run*
*Tags: taxprofiler deployment etl crawler athena minimizers*

---
*Observed: 2026-09-28T14:07:03.503Z*
