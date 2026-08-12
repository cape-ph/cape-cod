---
type: source
title: "Observation: Caerbannog ETL->crawler->Athena wiring validated end-to-end (dev)"
slug: obs-2026-08-06-caerbannog-etl-crawler-athena-wiring-validated-end-to-end-de
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: high
observed_at: 2026-08-06T19:50:48.062Z
tags: ["cape-cod", "caerbannog", "branch-363", "etl", "glue", "crawler", "athena", "validated", "e2e"]
source_context: "Branch 363 - end-to-end validation of caerbannog ETL and report wiring post-deploy"
---
# ⭐ Observation: Caerbannog ETL->crawler->Athena wiring validated end-to-end (dev)
Branch 363 caerbannog ETL + report wiring validated end-to-end in cape-cod-dev after deploy. Uploaded two test archives to s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/caerbannog-output/ (run-a full, run-b JSON-only). Both triggered the Glue job ccd-dlh-T-seqauto-ETL-caerbannog-results-34df755 within ~1s (each received the correct --OBJECT_KEY) and SUCCEEDED (~64-69s). Clean output landed under result-clean (ccd-dlh-t-seqauto-result-clean-vbkt-s3-fb0f529) exactly as designed: caerbannog_stoplight and caerbannog_cluster_estimates for both runs, caerbannog_aggregate only for run-a (confirming the aggregate-absent path for run-b), partitioned by caerbannog_run. The existing result-clean crawler (ccd-dlh-T-seqauto-result-clean-vbkt-crwl-gcrwl-1ceb6f5) registered result_caerbannog_aggregate, result_caerbannog_stoplight, result_caerbannog_cluster_estimates. The report's stoplight query for sample_id='abcdefghij' returns 2 active + 2 cleared target rows, so both report tables populate. Caveat: both test archives carry the same sample_id, so the sample-id-filtered report query returns duplicated rows across the two run partitions - expected for this test, avoided by distinct samples in production. Trigger isolation held: only the caerbannog job ran, not the bactopia ETLs.
*Relevance: high*

*Context: Branch 363 - end-to-end validation of caerbannog ETL and report wiring post-deploy*

*Tags: cape-cod caerbannog branch-363 etl glue crawler athena validated e2e*
---
*Observed: 2026-08-06T19:50:48.062Z*