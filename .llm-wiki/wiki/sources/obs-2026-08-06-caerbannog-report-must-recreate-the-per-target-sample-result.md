---
type: source
title:
    "Observation: Caerbannog report must recreate the per-target Sample Results
    Table (5 columns, from stoplight)"
slug: obs-2026-08-06-caerbannog-report-must-recreate-the-per-target-sample-result
status: observation
created: 2026-08-06
updated: 2026-08-11
relevance: high
observed_at: 2026-08-06T19:14:39.848Z
tags:
    [
        "cape-cod",
        "caerbannog",
        "report",
        "branch-363",
        "sample-results-table",
        "format",
    ]
source_context:
    "Branch 363 caerbannog report - correcting to the requested Sample Results
    Table format"
---

# ⭐ Observation: Caerbannog report must recreate the per-target Sample Results Table (5 columns, from stoplight)

Branch 363 report target format: the caerbannog report renders a per-target
sample results table sourced from the stoplight output's target detections. It
shows five fields per target - name, severity, assessment, confidence,
description - and by default hides cleared-status targets. This supersedes the
earlier two-table (category + cluster-estimates) report section; the
cluster-estimates table is removed from the report, though its data still lands
in the datalake. The underlying stoplight CSV columns are target_name /
target_severity / target_assessment / target_confidence / target_description;
sample_id is supplied by the partition, not a data column. _Relevance: high_

_Context: Branch 363 caerbannog report - correcting to the requested Sample
Results Table format_

_Tags: cape-cod caerbannog report branch-363 sample-results-table format_
---

_Observed: 2026-08-06T19:14:39.848Z_
