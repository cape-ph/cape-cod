---
type: source
title: "Observation: Fresh monitor started for deployed fixed DAG run"
tags:
  - taxprofiler
  - monitor
  - deployment
  - airflow
  - etl
status: observation
created: 2026-09-28
updated: 2026-09-28
slug: obs-2026-09-28-fresh-monitor-started-for-deployed-fixed-dag-run
relevance: medium
observed_at: 2026-09-28T13:53:20.987Z
source_context: Restarting the live taxprofiler pipeline monitor after deployment
---

# 🔍 Observation: Fresh monitor started for deployed fixed DAG run

Stopped stale monitor bg-12 and started bg-13 after the owner deployed the ETL/DAG fixes. AWS credentials are valid. New raw run `bactaxprof-01-fixed-20260928T134936Z` is present with pipeline-info params and one successful params ETL run; no Kraken2 report or completion marker is present yet. The fresh monitor has a baseline of one prior run and is watching the new run for ETL, clean output, crawler, and Athena transitions.

*Relevance: medium*
*Context: Restarting the live taxprofiler pipeline monitor after deployment*
*Tags: taxprofiler monitor deployment airflow etl*

---
*Observed: 2026-09-28T13:53:20.987Z*
