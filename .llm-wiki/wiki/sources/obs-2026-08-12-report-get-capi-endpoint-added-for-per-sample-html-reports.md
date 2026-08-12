---
type: source
title: "Observation: report/get CAPI endpoint added for per-sample HTML reports"
tags:
  - api
  - capi
  - reports
  - seqauto
  - artifacts
  - frontend
status: observation
created: 2026-08-12
updated: 2026-08-12
slug: obs-2026-08-12-report-get-capi-endpoint-added-for-per-sample-html-reports
relevance: high
observed_at: 2026-08-12T21:28:14.885Z
source_context: Wiring report/get endpoint in CAPI
---

# ⭐ Observation: report/get CAPI endpoint added for per-sample HTML reports

Added a new CAPI endpoint report/get (GET, query param sampleId) that returns a JSON map {"<report_name>": "<html>"} of all pre-rendered HTML reports for a sample. Report ETLs write to the seqauto tributary artifacts bucket at reports/<sample_id>/<report_name>.html (e.g. reports/<id>/rabits.html). Handler assets/api/capi/handlers/get_reports.py lists reports/<sampleId>/ (flat, .html only) via boto3 list_objects_v2 paginator and get_object, keys the map on the filename without .html, returns 200 {} for empty/unknown samples. Wiring in capeinfra/swimlanes/private.py _deploy_api: resolves the seqauto tributary (trib.code == "seqauto") artifacts VersionedBucket, sets env var REPORTS_BUCKET = bucket.bucket.bucket, and appends an S3 read+browse policy_statement (GetObject on arn/*, ListBucket on arn) to the shared CAPI lambda role; guarded with next(...)/None + warn() since the public stack seqauto tributary has no artifacts bucket. Spec route added to assets/api/capi/capi-openapi-301.yaml.j2 mirroring report/create (no per-route security; global security block applies API-wide), handler blocks (id get_reports_handler, name getreports, layer capi-all only) added to both Pulumi.cape-cod-dev.yaml and Pulumi.cape-cod-public.yaml since the spec is shared. No pulumi commands were run.

*Relevance: high*
*Context: Wiring report/get endpoint in CAPI*
*Tags: api capi reports seqauto artifacts frontend*

---
*Observed: 2026-08-12T21:28:14.885Z*
