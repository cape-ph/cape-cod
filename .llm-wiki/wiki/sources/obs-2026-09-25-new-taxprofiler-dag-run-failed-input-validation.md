---
type: source
title: "Observation: New taxprofiler DAG run failed input validation"
tags:
  - taxprofiler
  - airflow
  - dag
  - input-validation
  - kraken2
  - etl
status: observation
created: 2026-09-25
updated: 2026-09-25
slug: obs-2026-09-25-new-taxprofiler-dag-run-failed-input-validation
relevance: high
observed_at: 2026-09-25T20:34:35.771Z
source_context: Live background monitor detected a new taxprofiler test run
---

# ⭐ Observation: New taxprofiler DAG run failed input validation

The background monitor detected run `bactaxprof-01-dag-final-20260925T203154Z`. Its raw S3 prefix currently contains only `pipeline_info` artifacts and no Kraken2 report. The execution report shows nf-core/taxprofiler input validation failed because `fastq_1` points to `.../sequencing-reads.gz`, which does not match the required `.fq.gz` or `.fastq.gz` filename pattern. Five metadata ETL Glue runs are currently RUNNING; no Kraken2 ETL or report-ready output can occur until the DAG input path/filename is corrected and the run is retried.

*Relevance: high*
*Context: Live background monitor detected a new taxprofiler test run*
*Tags: taxprofiler airflow dag input-validation kraken2 etl*

---
*Observed: 2026-09-25T20:34:35.771Z*
