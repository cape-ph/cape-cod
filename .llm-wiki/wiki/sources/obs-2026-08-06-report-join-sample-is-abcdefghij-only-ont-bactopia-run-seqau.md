---
type: source
title: "Observation: Report join sample is abcdefghij (only ONT bactopia run); seqauto result bucket/catalog names"
slug: obs-2026-08-06-report-join-sample-is-abcdefghij-only-ont-bactopia-run-seqau
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: high
observed_at: 2026-08-06T19:43:48.807Z
tags: ["cape-cod", "caerbannog", "branch-363", "athena", "seqauto", "sample-id", "abcdefghij", "buckets"]
source_context: "Branch 363 - confirming caerbannog report join sample and result bucket/catalog facts"
---
# ⭐ Observation: Report join sample is abcdefghij (only ONT bactopia run); seqauto result bucket/catalog names
Confirmed the branch-363 report join sample empirically by querying Athena against the seqauto catalog (db ccd-dlh-t-seqauto-catalog_mczhqmdk). Running the report's exact metadata join - input_ccd_dlh_t_seqauto_input_clean_vbkt_s3_b1f75c7 joined to result_software_versions on input_file=sequencing_reads where parameter_name='--ont' - returns exactly one sample_id: 'abcdefghij' (the seqauto sequencing-reads test sample, per its meta.json). That is the only sample with a report-viable ONT bactopia run in cape-cod-dev, so caerbannog test archives must carry sample_id='abcdefghij' for the RABiTS Sample Results tables to render. Seqauto buckets: result-raw = ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821, result-clean = ccd-dlh-t-seqauto-result-clean-vbkt-s3-fb0f529. Bactopia result-clean tables are partitioned by bactopia_run (not sample_id); sample_id is a column inside the CSVs. Test archives updated in place at /home/lp76/projects/cape/test-data/rabits-out/guessed-daemon-output/ (run-a full, run-b JSON-only); drop under caerbannog-output/ in result-raw with a .tar.gz suffix to trigger the caerbannog-results ETL.
*Relevance: high*

*Context: Branch 363 - confirming caerbannog report join sample and result bucket/catalog facts*

*Tags: cape-cod caerbannog branch-363 athena seqauto sample-id abcdefghij buckets*
---
*Observed: 2026-08-06T19:43:48.807Z*