---
type: source
title: "Observation: Bactopia v4 output lacks complete legacy report metadata"
tags:
  - issue-379
  - bactopia
  - v4
  - metadata
  - etl
  - report
  - joins
  - output-derived
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-bactopia-v4-output-lacks-complete-legacy-report-metadata
relevance: high
observed_at: 2026-09-23T18:37:48.845Z
source_context: Representative S3 output metadata inspection
---

# ⭐ Observation: Bactopia v4 output lacks complete legacy report metadata

Inspected the representative v4.1 S3 output. `merged-results/meta.tsv` and `main/gather/*-meta.tsv` contain sample, runtype, pairing/compression, species, and genome size. Per-process `logs/versions.yml` files contain tool versions only. The output has a run-level `nf-reports/bactopia-report.html`, but no complete workflow software manifest. The output does not contain an authoritative input S3 object/parameter mapping, workflow Bactopia version, run date, selected profiler, or all report join fields. Some values can be derived from the run key/output layout, but the full legacy `result_software_versions` contract cannot be generated from Bactopia output alone without inference or an external run envelope. An ETL-produced output-derived table is viable for the fields present; a generic orchestration envelope is needed for the missing fields if the legacy report join remains.

*Relevance: high*
*Context: Representative S3 output metadata inspection*
*Tags: issue-379 bactopia v4 metadata etl report joins output-derived*

---
*Observed: 2026-09-23T18:37:48.845Z*
