---
type: source
title: "Align result-clean partitions with input-clean by reusing the sink prefix"
slug: datalake-align-result-clean-partitions-with-input-clean
status: insight
created: 2026-08-11
updated: 2026-08-11
category: architecture
---
# Align result-clean partitions with input-clean by reusing the sink prefix
When a downstream tool writes results back into the CAPE datalake keyed by the same partition prefix that the input-clean ETL produced, the result-clean ETL should recover that prefix from the object key and reuse it verbatim rather than inventing its own partition scheme.

In cape-cod, `etl_seqarchive.py` writes input-clean objects under a sink prefix like `sample_id=<id>/year=<y>/month=<m>/day=<d>/hour=<h>/minute=<min>/second=<s>/`. The caerbannog consumer uploads results to `caerbannog-output/<that same sink_prefix>/<sample_id>.tar.gz`. The result ETL strips `caerbannog-output/` and the trailing `/<archive>` and reuses the middle to key its outputs, so the `result_caerbannog_*` tables share the `sample_id/year/.../second` partitioning of the input-clean tables and Athena can join across the lake on the `sample_id` partition.

Two durable rules this enforces:
- A Hive/Athena partition column must not collide with a same-named data column. When `sample_id` is the partition, do NOT also emit a `sample_id` data column in the CSV; drop it from the column list (the partition supplies it). The input-clean `meta` table already works this way.
- Changing an existing table's partition layout (e.g. from a `caerbannog_run=` partition to `sample_id=/year=/...`) under the same table folder confuses the Glue crawler. A dev deploy must purge the old `result-clean` objects and drop the stale tables before re-crawling.

See [[sources/obs-2026-08-11-caerbannog-result-etl-rekeyed-to-input-clean-partitions-on-b]] and `concepts/testing-and-pulumi-preview-workflow`.
*Category: architecture*
---
*Captured: 2026-08-11*
## Related
_Add links to related pages._