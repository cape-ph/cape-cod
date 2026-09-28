---
type: source
title: Bactopia output-to-report extension contract
status: insight
created: 2026-09-24
updated: 2026-09-24
slug: bactopia-output-to-report-extension-contract
---

# Bactopia output-to-report extension contract

The current Bactopia integration establishes the extension seam for future pipeline reports. [[entities/assets-etl-scripts]] receives one raw S3 object per Glue invocation and writes crawler-friendly CSV to the clean result bucket. In seqauto, the result-clean crawler turns top-level output folders into `result_*` Athena tables, with `key=value` directories becoming partitions. [[entities/assets-report]] and [[entities/capemeta-module]] define a generic report pair: an Athena-backed data Lambda and an S3-hosted Jinja template selected by the `reportId` stored in CannedReportTable. The generic [[entities/assets-api-authorizer-and-spec]] route `/report/create` invokes that pair synchronously.

For a new pipeline, define the output contract and canonical sample/run identity first; choose the logical tributary and raw prefix; add a versioned DAP profile only when CAPE submits the pipeline; add a focused ETL adapter, Glue prefix/suffix registration, clean partition layout, fixtures, and crawler/Athena checks; then add `assets/report/<id>/data_function.py`, `template.html.j2`, and the `cape-cod:meta.report` entry. Do not embed physical bucket names in profiles. The orchestrator must pass an `--outdir` under the intended `result-raw` bucket and must refresh/poll the result-clean crawler before querying. The present implementation still needs a reusable contract validator and report-specific S3 permissions because the current report Lambda's Athena CTAS path has failed on missing input-clean `s3:GetObject`; API Gateway also limits the synchronous create path to 29 seconds. Sources: [[sources/obs-2026-09-24-bactopia-output-to-report-workflow-mapped]], [[sources/obs-2026-09-23-output-derived-metadata-etl-and-athena-join-verified]], [[sources/obs-2026-09-23-report-get-only-serves-pre-rendered-artifact-bodies]].



---
*Captured: 2026-09-24*

## Related

_Add links to related pages._
