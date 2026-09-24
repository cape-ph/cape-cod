---
type: source
title: "Observation: Athena exposed duplicate Bactopia run partition column"
tags:
  - issue-379
  - athena
  - glue
  - bactopia
  - v4
  - etl
  - schema
  - partition
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-athena-exposed-duplicate-bactopia-run-partition-column
relevance: high
observed_at: 2026-09-23T19:44:38.984Z
source_context: End-to-end validation finding and local correction
---

# ⭐ Observation: Athena exposed duplicate Bactopia run partition column

The deployed output-derived Bactopia report ETL replay succeeded, but querying `result_software_versions` failed with `HIVE_INVALID_METADATA` because `bactopia_run` was emitted in the CSV header while Glue also defines `bactopia_run` as the partition key. The local fix removes `bactopia_run` from the CSV data columns and relies on the partition value from `software_versions/bactopia_run=<run>/software_versions.csv`. Taxprofiler parent, Kraken2 child, MultiQC child, and ETL replay all succeeded before this catalog correction. The fix is uncommitted and requires deployment plus crawler revalidation.

*Relevance: high*
*Context: End-to-end validation finding and local correction*
*Tags: issue-379 athena glue bactopia v4 etl schema partition*

---
*Observed: 2026-09-23T19:44:38.984Z*
