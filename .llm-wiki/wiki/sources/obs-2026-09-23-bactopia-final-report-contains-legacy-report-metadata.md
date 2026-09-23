---
type: source
title: "Observation: Bactopia final report contains legacy report metadata"
tags:
  - issue-379
  - bactopia
  - v4
  - etl
  - report
  - metadata
  - output-derived
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-bactopia-final-report-contains-legacy-report-metadata
relevance: critical
observed_at: 2026-09-23T18:52:40.082Z
source_context: Representative S3 output investigation
---

# 🔴 Observation: Bactopia final report contains legacy report metadata

Representative Bactopia v4.1 `nf-reports/bactopia-report.html` contains the legacy report metadata needed for `result_software_versions`: full Nextflow command with `--ont` input, `--outdir`, and `--sample`; workflow version 4.1.0; Nextflow 26.04.6; workflow start and completion timestamps; and successful completion status. The run ID comes from the `bactopia-runs/<run>` output key, while sample collection metadata remains in input_meta. This makes the final report HTML a pipeline-specific late-stage ETL trigger and removes the need for a generic orchestration manifest for this report.

*Relevance: critical*
*Context: Representative S3 output investigation*
*Tags: issue-379 bactopia v4 etl report metadata output-derived*

---
*Observed: 2026-09-23T18:52:40.082Z*
