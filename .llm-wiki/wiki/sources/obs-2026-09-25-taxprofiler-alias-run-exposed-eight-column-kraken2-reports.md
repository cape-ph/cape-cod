---
type: source
title: "Observation: Taxprofiler alias run exposed eight-column Kraken2 reports"
tags:
  - taxprofiler
  - kraken2
  - etl
  - minimizer
  - parser
  - airflow
status: observation
created: 2026-09-25
updated: 2026-09-25
slug: obs-2026-09-25-taxprofiler-alias-run-exposed-eight-column-kraken2-reports
relevance: high
observed_at: 2026-09-25T21:14:43.588Z
source_context: Live monitor detected alias run ETL failure
---

# ⭐ Observation: Taxprofiler alias run exposed eight-column Kraken2 reports

The alias run `bactaxprof-01-dag-alias-20260925T210226Z` reached a Kraken2 report, so the prior Airflow input validation issue was corrected. The report uses eight tab-separated columns: percent, clade reads, direct reads, two minimizer fields, rank, taxid, and name. The deployed ETL expected six columns and failed with `Malformed Kraken2 report rows at source lines: 0-9`. Updated the local adapter to accept both six- and eight-column forms, selecting rank/taxid/name at columns 5/6/7 for the eight-column form. Added regression coverage; 22 taxprofiler ETL tests pass. This parser fix has not yet been deployed.

*Relevance: high*
*Context: Live monitor detected alias run ETL failure*
*Tags: taxprofiler kraken2 etl minimizer parser airflow*

---
*Observed: 2026-09-25T21:14:43.588Z*
