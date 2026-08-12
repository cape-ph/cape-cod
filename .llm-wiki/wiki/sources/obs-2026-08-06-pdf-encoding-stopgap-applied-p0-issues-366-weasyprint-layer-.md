---
type: source
title: "Observation: PDF encoding stopgap applied; P0 issues #366 (weasyprint layer dedup) and #367 (pre-generate reports in Airflow) filed"
slug: obs-2026-08-06-pdf-encoding-stopgap-applied-p0-issues-366-weasyprint-layer-
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: high
observed_at: 2026-08-06T20:40:45.002Z
tags: ["cape-cod", "reports", "weasyprint", "pdf", "issues", "p0", "airflow", "pregenerate", "branch-363"]
source_context: "Report PDF stopgap + filing follow-up P0 issues"
---
# ⭐ Observation: PDF encoding stopgap applied; P0 issues #366 (weasyprint layer dedup) and #367 (pre-generate reports in Airflow) filed
Applied the stopgap for the report PDF 500: removed the redundant encoding="utf-8" from the PDF branch of assets/api/capi/handlers/get_canned_report.py (weasyprint.HTML(string=report_html)), with a NOTE comment pointing at the P0 layer-dedup issue. report_html is already a decoded str so the encoding arg is a no-op; passing it is what forced override_encoding into the incompatible tinyhtml5. Kept the diff scoped (ruff hook tried to also merge an f-string and drop a blank line - reverted those). Pre-existing F841 headers-unused at line 258 left untouched (out of scope). Filed two P0 issues on cape-ph/cape-cod: #366 fix(reports) dedup+upgrade weasyprint lambda layers (report-gen weasyprint==66.0/tinyhtml5 2.1.0 vs kotify-cpu weasyprint 68.0/tinyhtml5 2.0.0 collision; keep kotify native libs, single coherent weasyprint, check kotify cloud-print-utils https://github.com/kotify/cloud-print-utils for a self-consistent release, upgrade versions); #367 feat(reports) pre-generate canned reports in the bactopia Airflow workflow and serve pre-rendered artifacts from storage so the URL just fetches - removes the 29s API Gateway timeout risk and makes PDF viable (handler TODO already wants async generate-store-notify). #367 is a stretch item to attack after the primary caerbannog integration lands. Repo label for highest priority is literally "P0".
*Relevance: high*

*Context: Report PDF stopgap + filing follow-up P0 issues*

*Tags: cape-cod reports weasyprint pdf issues p0 airflow pregenerate branch-363*
---
*Observed: 2026-08-06T20:40:45.002Z*