---
type: source
title: "Observation: Branch 363 caerbannog ETL scaffolding landed + notifier collision-safety mechanics"
slug: obs-2026-08-06-branch-363-caerbannog-etl-scaffolding-landed-notifier-collis
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: high
observed_at: 2026-08-06T18:20:45.926Z
tags: ["cape-cod", "caerbannog", "seqauto", "etl", "trigger", "collision-safety", "branch-363", "commit-5ef6122"]
source_context: "Implementing branch 363 caerbannog result ETL scaffolding"
---
# ⭐ Observation: Branch 363 caerbannog ETL scaffolding landed + notifier collision-safety mechanics
Branch 363 ETL/trigger scaffolding landed (commit 5ef6122). Added assets/etl/etl_caerbannog_results.py plus a caerbannog-results ETL entry in the seqauto tributary of Pulumi.cape-cod-dev.yaml (src result-raw, sink result-clean, prefix caerbannog-output, suffixes gz/tar, max_concurrent_runs 5) and its script asset registration (etl-caerbannog-results). Output written under top-level folders caerbannog_aggregate / caerbannog_stoplight / caerbannog_cluster_estimates, partitioned by caerbannog_run=<run_id> (run_id derived from the archive basename), so the existing result-clean crawler catalogs them as result_caerbannog_* tables.

Collision-safety verified against the notifier logic (assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py): for the ETL path it deconstructs the object key, takes suffix = rpartition('.') (so archive.tar.gz -> suffix 'gz'), and walks every ancestor prefix from longest to shortest calling EtlTable.get_etls(bucket, prefix), queuing an ETL when a registered (bucket, prefix) exists AND the suffix is in that ETL's suffixes. Because it keeps walking after a match, one object can trigger multiple ETLs at different registered prefix depths (this is why a bactopia object under pipeline-output/bactopia-runs already double-fires bactopia-results and bactopia-samples - pre-existing). caerbannog is safe because prefix caerbannog-output is disjoint from pipeline-output* and suffixes gz/tar are disjoint from tsv/yml/txt, so neither dataset can trigger the other. result-raw has no notify rules (only seqauto input-clean does), so the archive drives only the ETL path.

Format-dependent logic is stubbed behind seams for the second pass: derive_sample_id (sample name from filename vs sidecar metadata TBD), normalize_stoplight and normalize_cluster_estimates (currently a generic one-level flatten that json-encodes nested values and unions keys for a stable CSV header). Lint clean (ruff check + ruff format, 80-col). json.loads is wrapped to name the offending archive member then re-raise (pi-lens blocker; stricter than the bare json.load in etl_seqarchive.py). Next: report changes as a separate commit group once schemas arrive or as best-guess.
*Relevance: high*

*Context: Implementing branch 363 caerbannog result ETL scaffolding*

*Tags: cape-cod caerbannog seqauto etl trigger collision-safety branch-363 commit-5ef6122*
---
*Observed: 2026-08-06T18:20:45.926Z*