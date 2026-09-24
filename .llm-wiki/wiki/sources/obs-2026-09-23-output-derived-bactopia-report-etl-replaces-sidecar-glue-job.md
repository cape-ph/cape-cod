---
type: source
title: "Observation: Output-derived Bactopia report ETL replaces sidecar Glue job"
tags:
  - issue-379
  - bactopia
  - v4
  - etl
  - report
  - output-derived
  - pulumi
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-output-derived-bactopia-report-etl-replaces-sidecar-glue-job
relevance: critical
observed_at: 2026-09-23T19:02:32.499Z
source_context: Replacing orchestration sidecar metadata with terminal workflow-report ETL
---

# 🔴 Observation: Output-derived Bactopia report ETL replaces sidecar Glue job

Revised the uncommitted metadata design after inspecting representative Bactopia v4 output. The final `nf-reports/bactopia-report.html` contains workflow command, Bactopia version, Nextflow version, input, output root, sample, and workflow times. The existing seqauto `bactopia-results` ETL now parses that terminal report artifact and writes `software_versions/bactopia_run=<run>/software_versions.csv`; the separate JSON sidecar and `bactopia-run-metadata` Glue job were removed. Pulumi preview now shows three expected updates: ETL script object, ETLAttrs suffixes adding `html`, and the accepted recurring GTRI SSO drift. Focused tests pass 36; no commit or deployment was made.

*Relevance: critical*
*Context: Replacing orchestration sidecar metadata with terminal workflow-report ETL*
*Tags: issue-379 bactopia v4 etl report output-derived pulumi*

---
*Observed: 2026-09-23T19:02:32.499Z*
