---
type: source
title: "Observation: Branch 363 caerbannog archive input contract and branch conventions"
slug: obs-2026-08-06-branch-363-caerbannog-archive-input-contract-and-branch-conv
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: high
observed_at: 2026-08-06T18:10:49.550Z
tags: ["cape-cod", "caerbannog", "seqauto", "etl", "archive", "tar-gz", "result-raw", "branch-363"]
source_context: "Q&A planning for branch 363 caerbannog result ETL + report"
---
# ⭐ Observation: Branch 363 caerbannog archive input contract and branch conventions
Branch 363 input contract from the caerbannog consumer (all filenames strictly notional/TBD until real format lands): the consumer writes a single tar.gz archive to the seqauto result-raw bucket under prefix caerbannog-output, one archive per consumer run = one user upload. Archive layout: aggregate.csv at the root (placeholder for a pre-aggregated CSV; column names + descriptions available), plus individual-outputs/ containing per-sample paired JSON files stoplight-N.json and cluster-estimates-N.json (stoplight and cluster-estimates are part of the consumer's default filename nomenclature; schemas + examples available). Sample name is the join key for the report; it will be encoded in filenames or supplied via a sidecar metadata file - TBD, so the ETL should isolate sample-id derivation as one swappable step. Output stays CSV for now (columnar move is datalake-wide, tracked in #364). The new ETL (config entry with src: result-raw, sink: result-clean, prefix caerbannog-output, suffix likely json/gz/tar) must NOT collide with the existing bactopia result-raw ETLs (bactopia-results prefix pipeline-output/bactopia-runs suffixes tsv/yml; bactopia-samples prefix pipeline-output suffixes tsv/txt) - caerbannog-output prefix is disjoint. Follow etl_seqarchive.py for tar.gz unpacking precedent. Branch conventions: dev config only (Pulumi.cape-cod-dev.yaml; public is auto-generated), commits grouped by function (ETL/trigger separate from report, multiple commits allowed per function as clarity arrives), GitHub issue #363.
*Relevance: high*

*Context: Q&A planning for branch 363 caerbannog result ETL + report*

*Tags: cape-cod caerbannog seqauto etl archive tar-gz result-raw branch-363*
---
*Observed: 2026-08-06T18:10:49.550Z*