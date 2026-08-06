---
type: source
title: "Observation: Caerbannog report must recreate the per-target Sample Results Table (5 columns, from stoplight)"
slug: obs-2026-08-06-caerbannog-report-must-recreate-the-per-target-sample-result
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: high
observed_at: 2026-08-06T19:14:39.848Z
tags: ["cape-cod", "caerbannog", "report", "branch-363", "sample-results-table", "format"]
source_context: "Branch 363 caerbannog report - correcting to the requested Sample Results Table format"
---
# ⭐ Observation: Caerbannog report must recreate the per-target Sample Results Table (5 columns, from stoplight)
Branch 363 report target format clarified: the caerbannog report table must recreate the RABiTS "Sample Results Table" (documented as Table 3 / section 8.3 in the confidential consumer user guide, not to be reproduced in the wiki). It is a per-target table sourced from the stoplight output's target detections, with these columns: target name, severity, assessment, confidence, description. Three documented columns are explicitly NOT wanted: the assessment status symbol, alert level, and field notes. The documented default view also excludes cleared-status targets. This supersedes the earlier two-table (category + cluster-estimates) report section, which was compelling but not the requested format; the cluster-estimates table is being removed from the report (the data still lands in the datalake). Column-label wording avoids the phrase the user asked to drop; the underlying stoplight CSV columns are target_name/target_severity/target_assessment/target_confidence/target_description keyed by sample_id.
*Relevance: high*

*Context: Branch 363 caerbannog report - correcting to the requested Sample Results Table format*

*Tags: cape-cod caerbannog report branch-363 sample-results-table format*
---
*Observed: 2026-08-06T19:14:39.848Z*