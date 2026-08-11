---
type: source
title: "Observation: Reworked caerbannog result ETL validated end-to-end on dev"
slug: obs-2026-08-11-reworked-caerbannog-result-etl-validated-end-to-end-on-dev
status: observation
created: 2026-08-11
updated: 2026-08-11
relevance: high
observed_at: 2026-08-11T20:12:35.560Z
tags: ["caerbannog", "etl", "seqauto", "datalake", "validation", "branch-363"]
source_context: "Live dev test of branch 363 caerbannog result ETL rework"
---
# ⭐ Observation: Reworked caerbannog result ETL validated end-to-end on dev
The branch 363 rework of assets/etl/etl_caerbannog_results.py was validated on a live dev run through the full seqauto chain: input-raw/unprocessed/ upload -> etl_seqarchive -> input-clean (41 split reads + meta/manifest under a sample_id=/year=/.../second= sink prefix) -> consumer VM -> result-raw/caerbannog-output/<sink_prefix>/<sample_id>.tar.gz -> etl_caerbannog_results -> result-clean.

The result-clean outputs matched the intended contract exactly. All three landed under one identical sink prefix reused verbatim from the result-raw object key (sample_id=abcdefghij/year=2026/month=8/day=11/hour=20/minute=3/second=12):
- caerbannog_stoplight/<sink_prefix>/stoplight.csv
- caerbannog_cluster_estimates/<sink_prefix>/cluster_estimates.csv
- caerbannog-report/<sink_prefix>/report.html

CSV headers had no sample_id data column (sample_id is the partition): stoplight started rule_set_version,software_version,status,... (1 header + 1 data row); cluster started rule_set_version,... (1 header + 25 data rows). parse_sink_prefix handled the live key correctly. The HTML report was well-formed (DOCTYPE..</html>) with a single active-results table (one row) and no cleared-threats section for this sample.

VM permission errors blocked two earlier attempts (VM needs read on input-clean and write on result-raw via its instance profile); after that was fixed the third upload flowed straight through. The result-clean crawler still needs to run to catalog result_caerbannog_stoplight and result_caerbannog_cluster_estimates with the new partitioning before the report data function query resolves; the crawler excludes caerbannog-report/**.
*Relevance: high*

*Context: Live dev test of branch 363 caerbannog result ETL rework*

*Tags: caerbannog etl seqauto datalake validation branch-363*
---
*Observed: 2026-08-11T20:12:35.560Z*