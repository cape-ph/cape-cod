---
type: source
title: "Observation: Branch 363 absorbed PR #369; caerbannog raw-result ETL implemented and validated"
slug: obs-2026-08-11-branch-363-absorbed-pr-369-caerbannog-raw-result-etl-impleme
status: observation
created: 2026-08-11
updated: 2026-08-11
relevance: high
observed_at: 2026-08-11T14:17:48.072Z
tags: ["cape-cod", "caerbannog", "etl", "branch-363", "pr-369-merged", "raw-result", "branch-topology"]
source_context: "Returning to branch 363; confirming raw-result ETL is implemented and validated"
---
# ⭐ Observation: Branch 363 absorbed PR #369; caerbannog raw-result ETL implemented and validated

Branch topology update (cape-cod): PR #369 (368-fix-notifier-messagegroupid-128-limit) was merged into branch 363-featseqauto-add-new-raw-result-etl-and-update-report-to-show-data-from-it (merge commit d608ac5). So branch 363 now contains the notifier FIFO MessageGroupId 128-char fix (2a7b483) and the togglable->toggleable typo fix (ffe1dd7) on top of all the caerbannog raw-result ETL work. Current checkout is 363. The caerbannog raw-result ETL (assets/etl/etl_caerbannog_results.py) is implemented and was validated locally + end-to-end (crawler->Athena) in dev as of 2026-08-06.

The ETL's format-dependent seams (archive member handling, the JSON normalizers, and the CSV/Athena column schemas) are intentionally NOT recorded here because the consumer output format is EAR-controlled. See assets/etl/etl_caerbannog_results.py for the current field handling; it must move in lockstep with the report consumer assets/report/bactopia-single-sample-analysis/data_function.py, and both are keyed on sample_id.
*Relevance: high*

*Context: Returning to branch 363; confirming raw-result ETL is implemented and validated*

*Tags: cape-cod caerbannog etl branch-363 pr-369-merged raw-result branch-topology*
---

*Observed: 2026-08-11T14:17:48.072Z*
