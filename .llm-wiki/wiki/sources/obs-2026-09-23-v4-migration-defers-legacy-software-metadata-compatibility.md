---
type: source
title: "Observation: V4 migration defers legacy software metadata compatibility"
tags:
  - issue-379
  - bactopia
  - v4
  - metadata
  - etl
  - reporting
  - taxprofiler
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-v4-migration-defers-legacy-software-metadata-compatibility
relevance: high
observed_at: 2026-09-23T16:40:18.873Z
source_context: Owner scope decision for v4 migration completion
---

# ⭐ Observation: V4 migration defers legacy software metadata compatibility

Owner confirmed that CAPE will not support Bactopia v3.x going forward, and no current users depend on its output. Leave the existing v3 software_versions handling and historical fixtures alone for now. For v4, add the needed run metadata under a stable per-run crawlable prefix with future report-join fields, rather than forcing v4 to reproduce the legacy file. After the end-to-end path works, replace selected forward data with Bactopia v4.1 data. A representative Bactopia v4.1 run followed by taxprofiler Kraken2 on the required Bactopia output, ETL ingestion, and report generation is required acceptance evidence.

*Relevance: high*
*Context: Owner scope decision for v4 migration completion*
*Tags: issue-379 bactopia v4 metadata etl reporting taxprofiler*

---
*Observed: 2026-09-23T16:40:18.873Z*
