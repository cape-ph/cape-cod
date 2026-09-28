---
type: source
title: "Observation: Fixed taxprofiler sample is report-ready in Athena"
tags:
  - taxprofiler
  - report
  - athena
  - api
  - crawler
status: observation
created: 2026-09-28
updated: 2026-09-28
slug: obs-2026-09-28-fixed-taxprofiler-sample-is-report-ready-in-athena
relevance: high
observed_at: 2026-09-28T14:28:10.460Z
source_context: Requesting the deployed HTML report for the fixed sample
---

# ⭐ Observation: Fixed taxprofiler sample is report-ready in Athena

Verified live sample `bactaxprof-01-fixed-20260928T134936Z`: clean `kraken2_taxa` and `kraken2_summary` objects are present, the result-clean crawler is READY after a successful crawl, and both Athena tables have the sample/database partition. The report endpoint is `https://api.cape-dev.org/capi-dev/report/create?sampleId=bactaxprof-01-fixed-20260928T134936Z&reportId=taxprofiler-kraken2&format=html`. Agent-side curl could not resolve `api.cape-dev.org`, so HTML response was not independently fetched; this is a local DNS/network limitation, not an Athena readiness failure. The monitor remains active as bg-13.

*Relevance: high*
*Context: Requesting the deployed HTML report for the fixed sample*
*Tags: taxprofiler report athena api crawler*

---
*Observed: 2026-09-28T14:28:10.460Z*
