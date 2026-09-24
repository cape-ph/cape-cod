---
type: source
title: "Observation: Bactopia v3.2 and v4.1 QC paths are structurally similar"
tags:
  - bactopia
  - qc
  - v3
  - v4
  - nanoplot
  - comparison
status: observation
created: 2026-09-15
updated: 2026-09-15
slug: obs-2026-09-15-bactopia-v3-2-and-v4-1-qc-paths-are-structurally-similar
relevance: high
observed_at: 2026-09-15T18:31:00.709Z
source_context: Bactopia v3.2/v4.1 QC source comparison and EC2 run
---

# ⭐ Observation: Bactopia v3.2 and v4.1 QC paths are structurally similar

Source comparison of Bactopia v3.2.0 `modules/local/bactopia/qc/main.nf` and v4.1.0 `modules/bactopia/qc/main.nf` shows the same major ONT QC phases: nanoq filtering, ONT error correction skipped, coverage reduction skipped when genome size is zero, pre/post fastq-scan, original/final NanoPlot by default, and final read checks. v4 refactors the module and changes output organization to supplemental/process outputs, uses `bactopia-check-fastqs` instead of v3's `check-fastqs.py`, and adds/renames control parameters such as `skip_qc`, `skip_qc_plots`, and `skip_fastq_check`. The v4.1 run produced original NanoPlot outputs but not final QC outputs before the QC child was killed after about 85 minutes; v3 QC completed in roughly 2.6 minutes on the same concatenated input. A targeted v4 `--skip_qc_plots` resume test is the next isolation step to determine whether NanoPlot is the runtime bottleneck.

*Relevance: high*
*Context: Bactopia v3.2/v4.1 QC source comparison and EC2 run*
*Tags: bactopia qc v3 v4 nanoplot comparison*

---
*Observed: 2026-09-15T18:31:00.709Z*
