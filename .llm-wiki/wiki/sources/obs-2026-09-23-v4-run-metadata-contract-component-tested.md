---
type: source
title: "Observation: V4 run metadata contract component tested"
tags:
  - issue-379
  - bactopia
  - v4
  - metadata
  - etl
  - report
  - contract
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-v4-run-metadata-contract-component-tested
relevance: high
observed_at: 2026-09-23T17:53:46.516Z
source_context: Implementing the v4 metadata component and contract tests
---

# ⭐ Observation: V4 run metadata contract component tested

Implemented the next metadata slice in assets/etl/etl_bactopia_results.py as BactopiaOutputContractV1Adapter.parse_run_manifest. It validates schemaVersion, run identity, pipeline/Nextflow versions, output/QC paths, selected profiler, and S3 input mappings, then emits crawlable report-join rows including bactopia_run, sample_id, run_date, input_file, parameter_name, output root, QC path, and contract versions. Added tests/fixtures/bactopia-v4/run-manifest.json plus schema and non-S3 input rejection tests. Focused ETL, DAP, and pipeline asset tests pass: 35 passed. Glue trigger wiring and representative end-to-end validation remain next.

*Relevance: high*
*Context: Implementing the v4 metadata component and contract tests*
*Tags: issue-379 bactopia v4 metadata etl report contract*

---
*Observed: 2026-09-23T17:53:46.516Z*
