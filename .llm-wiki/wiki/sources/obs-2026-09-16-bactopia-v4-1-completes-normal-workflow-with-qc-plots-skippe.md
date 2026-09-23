---
type: source
title: "Observation: Bactopia v4.1 completes normal workflow with QC plots skipped"
tags:
  - bactopia
  - v4
  - migration
  - output
  - layout
  - qc
  - success
status: observation
created: 2026-09-16
updated: 2026-09-16
slug: obs-2026-09-16-bactopia-v4-1-completes-normal-workflow-with-qc-plots-skippe
relevance: critical
observed_at: 2026-09-16T13:56:59.876Z
source_context: Bactopia v4.1 EC2 run and output comparison
---

# 🔴 Observation: Bactopia v4.1 completes normal workflow with QC plots skipped

On the resized m5.large EC2 launcher, Bactopia v4.1.0 with Nextflow 26.04.6 and `-profile docker` completed successfully with `--skip_qc_plots true` in 24m58s. DATASETS, GATHER, QC, assembler, sketcher, Prokka, AMRFinderPlus, MLST, and merged reports completed; one assembler retry recovered. Output comparison against the partial v3.2 baseline shows equal QC FASTQ content size (101,425,901 bytes) but a path change: v3 uses `main/qc/<sample>.fastq.gz` and `main/qc/summary/*`, while v4 uses `main/qc/<sample>_ONT.fastq.gz` and `main/qc/supplemental/*`. V4 also publishes `main/sketcher`, `main/annotator/prokka`, and `tools/amrfinderplus`/`tools/mlst`. Kraken2 v4 output and report compatibility remain to be tested.

*Relevance: critical*
*Context: Bactopia v4.1 EC2 run and output comparison*
*Tags: bactopia v4 migration output layout qc success*

---
*Observed: 2026-09-16T13:56:59.876Z*
