---
type: source
title: "Observation: Output-derived metadata ETL and Athena join verified"
tags:
  - issue-379
  - bactopia
  - v4
  - etl
  - athena
  - report
  - metadata
  - taxprofiler
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-output-derived-metadata-etl-and-athena-join-verified
relevance: critical
observed_at: 2026-09-23T20:02:52.996Z
source_context: Post-deployment output-derived ETL and catalog validation
---

# 🔴 Observation: Output-derived metadata ETL and Athena join verified

After deployment, the corrected Bactopia report ETL replay succeeded. The result-clean crawler initially retained a stale duplicate `bactopia_run` data column alongside the partition, causing HIVE_INVALID_METADATA. With owner approval, repaired only the Glue catalog schema by removing the duplicate data column and retaining the partition. The subsequent Athena query succeeded and returned `bactopia_run`, sample_id, workflow times, Bactopia 4.1.0, Nextflow 26.04.6, input path, output root, QC path, output contract, and parameter. The representative taxprofiler parent, Kraken2 child, and MultiQC child also succeeded. Full report join remains pending because the replay sample name does not match an existing input_meta sample.

*Relevance: critical*
*Context: Post-deployment output-derived ETL and catalog validation*
*Tags: issue-379 bactopia v4 etl athena report metadata taxprofiler*

---
*Observed: 2026-09-23T20:02:52.996Z*
