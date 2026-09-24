---
type: source
title: "Observation: Bactopia v4.1 Kraken2 tool ignores ONT input slot"
tags:
  - bactopia
  - v4
  - kraken2
  - ont
  - bug
  - migration
status: observation
created: 2026-09-16
updated: 2026-09-16
slug: obs-2026-09-16-bactopia-v4-1-kraken2-tool-ignores-ont-input-slot
relevance: critical
observed_at: 2026-09-16T15:12:27.752Z
source_context: Bactopia v4.1 Kraken2 EFS-local test
---

# 🔴 Observation: Bactopia v4.1 Kraken2 tool ignores ONT input slot

The v4.1 tool-specific Kraken2 run reached the correct entrypoint and local EFS Bactopia output, but its KRAKEN2 module generated `k2 classify ... --paired null null`. The v4 `BactopiaTools._collectInputs` code correctly models ONT reads in the `lr` slot when it finds `main/qc/<sample>_ONT.fastq.gz` and `main/assembler/supplemental/ont.txt`. However, `modules/kraken2/main.nf` calculates `meta.single_end` only from `se`, `r1`, and `r2`, then sets `read_inputs = meta.single_end ? se : r1 r2`, ignoring `lr`. This causes `FileNotFoundError: null` in the k2 container. V3.2 treated the ONT FASTQ as its single-end slot and succeeded. This is a Bactopia v4.1 Kraken2 ONT-input bug/limitation, independent of the S3 and Batch fixes.

*Relevance: critical*
*Context: Bactopia v4.1 Kraken2 EFS-local test*
*Tags: bactopia v4 kraken2 ont bug migration*

---
*Observed: 2026-09-16T15:12:27.752Z*
