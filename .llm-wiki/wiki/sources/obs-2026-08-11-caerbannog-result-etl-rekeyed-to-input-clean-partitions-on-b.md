---
type: source
title: "Observation: Caerbannog result ETL rekeyed to input-clean partitions on branch 363"
slug: obs-2026-08-11-caerbannog-result-etl-rekeyed-to-input-clean-partitions-on-b
status: observation
created: 2026-08-11
updated: 2026-08-11
relevance: high
observed_at: 2026-08-11T18:54:09.936Z
tags: ["seqauto", "caerbannog", "etl", "glue", "athena", "partitions"]
source_context: "seqauto caerbannog result ETL rework (branch 363)"
---
# ⭐ Observation: Caerbannog result ETL rekeyed to input-clean partitions on branch 363
Reworked assets/etl/etl_caerbannog_results.py (cape-cod, branch 363) to the current VM upload contract. The consumer delivers one <sample_id>.tar.gz to result-raw under caerbannog-output/<sink_prefix>/<sample_id>.tar.gz, where <sink_prefix> is the verbatim input-clean partition prefix (sample_id=.../year=.../.../second=...) written by etl_seqarchive.py. Key changes: (1) new parse_sink_prefix(object_key, root_prefix) recovers that prefix from the object key and reuses it verbatim so result-clean partitions align with input-clean; (2) result_meta.json now drives member lookup via meta["stoplight"] and meta["cluster_estimates"] instead of suffix-globbing; the aggregate table/CSV is gone (upstream tool removed); (3) sample_id is no longer written as a CSV data column since it is the partition column (Hive/Athena forbid a data column with the same name); (4) outputs are re-keyed to caerbannog_stoplight/<sink_prefix>/stoplight.csv and caerbannog_cluster_estimates/<sink_prefix>/cluster_estimates.csv, dropping the old caerbannog_run partition; (5) a TEMPORARY jinja2-rendered self-contained HTML report is written to caerbannog-report/<sink_prefix>/report.html with a loud TODO(#363) that report rendering must move out of the ETL. Config: added jinja2==3.1.6 to the caerbannog-results Glue job pymodules and excludes: ["caerbannog-report/**"] to the seqauto result-clean crawler in Pulumi.cape-cod-dev.yaml. Validated with a local stubbed-EtlJob harness against the real example archive: correct sink_prefix reuse, no sample_id data column, well-formed HTML. Deploy requires purging old dev caerbannog_* result-clean objects and dropping stale tables (partition scheme changed) before re-crawling.
*Relevance: high*

*Context: seqauto caerbannog result ETL rework (branch 363)*

*Tags: seqauto caerbannog etl glue athena partitions*
---
*Observed: 2026-08-11T18:54:09.936Z*