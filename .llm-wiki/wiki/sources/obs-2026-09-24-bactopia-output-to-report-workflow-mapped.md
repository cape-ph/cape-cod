---
type: source
title: "Observation: Bactopia output-to-report workflow mapped"
tags:
  - bactopia
  - etl
  - glue
  - athena
  - reports
  - s3
  - workflow
status: observation
created: 2026-09-24
updated: 2026-09-24
slug: obs-2026-09-24-bactopia-output-to-report-workflow-mapped
relevance: high
observed_at: 2026-09-24T18:32:41.053Z
source_context: Repository reconnaissance for a reusable new-pipeline-to-report workflow
---

# ⭐ Observation: Bactopia output-to-report workflow mapped

Mapped the current CAPE Cod Bactopia path end to end. Bactopia output is caller-selected through --outdir and must land under the logical seqauto result-raw bucket at pipeline-output/bactopia-runs/<run>; the DAP profile and Nextflow kickstart do not choose that bucket automatically. S3 ObjectCreated events flow through assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py, ETLAttrs DDB, FIFO SQS, and assets/trigger-functions/sqs/sqs_etl_job_trigger_lambda.py into Glue. Pulumi.cape-cod-dev.yaml registers assets/etl/etl_bactopia_results.py for tsv/yml/html and etl_bactopia_samples.py for tsv/txt. The results ETL writes partitioned CSVs such as mlst/bactopia_run=<run>/mlst.csv, amrfinderplus/bactopia_run=<run>/amrfinderplus.csv, and software_versions/bactopia_run=<run>/software_versions.csv; the v4 software metadata comes from nf-reports/bactopia-report.html and excludes bactopia_run from the CSV because Glue supplies it as a partition. The seqauto result-clean crawler exposes result_* Athena tables. assets/report/bactopia-single-sample-analysis/data_function.py queries input_meta, result_software_versions, result_sourmash_gtdb_rs207_k31, and result_amrfinderplus, then assets/api/capi/handlers/get_canned_report.py serves GET /report/create by loading a report item from CannedReportTable, invoking the configured data Lambda, rendering the S3-hosted Jinja template, and returning HTML or PDF. New report types normally require a new ETL contract/config entry, fixtures and crawler validation, assets/report/<report-id>/data_function.py and template.html.j2, and a cape-cod:meta.report entry; the generic route needs no new handler. Important current gaps are caller-owned output bucket selection, crawler refresh timing, report Lambda S3 permissions for Athena CTAS inputs, the 29-second API Gateway timeout, and hard-coded seqauto/sample/--ont joins in the current report data function.

*Relevance: high*
*Context: Repository reconnaissance for a reusable new-pipeline-to-report workflow*
*Tags: bactopia etl glue athena reports s3 workflow*

---
*Observed: 2026-09-24T18:32:41.053Z*
