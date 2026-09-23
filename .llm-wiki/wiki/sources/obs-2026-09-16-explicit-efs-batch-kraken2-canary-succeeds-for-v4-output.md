---
type: source
title: "Observation: Explicit EFS Batch Kraken2 canary succeeds for v4 output"
tags:
  - standalone
  - kraken2
  - efs
  - batch
  - v4
  - validation
status: observation
created: 2026-09-16
updated: 2026-09-16
slug: obs-2026-09-16-explicit-efs-batch-kraken2-canary-succeeds-for-v4-output
relevance: critical
observed_at: 2026-09-16T16:30:35.077Z
source_context: Explicit ECS-managed EFS Kraken2 canary
---

# 🔴 Observation: Explicit EFS Batch Kraken2 canary succeeds for v4 output

Temporary Batch job `c64f18e7-e055-42f4-8849-eb47d9c01a75` with job definition `kraken2-efs-canary-20260916162428:1` mounted EFS via ECS-managed `efsVolumeConfiguration`, bypassing the missing analysis-host mount. The child saw `/mnt/nextflow_shared_data`, the 7.5 GiB `hash.k2d`, and the v4.1 ONT QC FASTQ. The `bactopia-teton:1.1.4` `k2 classify` command completed in 2.913 seconds, processed 17,563 sequences, classified 17,562, and left 1 unclassified. The report had 360 lines and its head/tail matched the v3.2 Kraken2 baseline. This proves Kraken2/database/input/Batch/EFS work independently of the Bactopia v4 tool wrapper. The v4 report was only persisted in container /tmp, so exact byte comparison remains pending. Temporary job definition cleanup remains pending approval.

*Relevance: critical*
*Context: Explicit ECS-managed EFS Kraken2 canary*
*Tags: standalone kraken2 efs batch v4 validation*

---
*Observed: 2026-09-16T16:30:35.077Z*
