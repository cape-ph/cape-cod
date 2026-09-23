---
type: source
title: "Observation: report/get only serves pre-rendered artifact bodies"
tags:
  - issue-379
  - report-get
  - artifacts
  - aiken
  - taxprofiler
  - bactopia
  - external-dag
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-report-get-only-serves-pre-rendered-artifact-bodies
relevance: critical
observed_at: 2026-09-23T20:24:05.215Z
source_context: S3 and deployed report/get validation for new branch data
---

# 🔴 Observation: report/get only serves pre-rendered artifact bodies

Deployed `report/get` was invoked successfully for historical Aiken sample `micah-test-2`, returning `bactopia`, `kraken2`, and `rabits` HTML bodies with `createdAt` values. Read-only S3 inspection found no `reports/` objects for the new Issue 379 sample or replay prefixes. The new v4 Bactopia ETL writes result-clean metadata and the taxprofiler run writes a raw Kraken2 text report; neither publishes a `reports/<sample_id>/...html` artifact in CAPE Cod. `get_reports.py` is read-only, so the current artifact bodies are produced by the external report-generation path or prior demo workflow. `rabits.html` is the exception: the CAPE Cod Caerbannog ETL writes that artifact.

*Relevance: critical*
*Context: S3 and deployed report/get validation for new branch data*
*Tags: issue-379 report-get artifacts aiken taxprofiler bactopia external-dag*

---
*Observed: 2026-09-23T20:24:05.215Z*
