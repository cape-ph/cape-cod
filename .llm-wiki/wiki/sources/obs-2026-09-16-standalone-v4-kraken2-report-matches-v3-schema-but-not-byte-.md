---
type: source
title: "Observation: Standalone v4 Kraken2 report matches v3 schema but not byte-for-byte"
tags:
  - kraken2
  - v4
  - report
  - comparison
  - migration
  - taxprofiler
status: observation
created: 2026-09-16
updated: 2026-09-16
slug: obs-2026-09-16-standalone-v4-kraken2-report-matches-v3-schema-but-not-byte-
relevance: critical
observed_at: 2026-09-16T16:44:53.222Z
source_context: Persisted standalone v4 report versus v3 baseline comparison
---

# 🔴 Observation: Standalone v4 Kraken2 report matches v3 schema but not byte-for-byte

The explicit ECS-managed EFS canary persisted the standalone v4 report at `batch_job_scratch/bactopia41-ec2-20260915143928/standalone-efs-canary-v4/v4-report.txt`. Full comparison with the v3.2 report found 360 rows in both and identical taxid sets, classification totals, and head/tail rows, but reports are not byte-identical. Internal differences include taxonomy rank codes (`R2` in v3 versus `D` in v4 for Bacteria) and row ordering for low-count taxa. The existing DAG parser parsed all 360 v4 rows and rendered 147,823 bytes of HTML containing the sample and Bacteria entries. This supports standalone Kraken2 migration: the report shape is compatible, but semantic rank/order differences should be documented and any downstream expectations checked.

*Relevance: critical*
*Context: Persisted standalone v4 report versus v3 baseline comparison*
*Tags: kraken2 v4 report comparison migration taxprofiler*

---
*Observed: 2026-09-16T16:44:53.222Z*
