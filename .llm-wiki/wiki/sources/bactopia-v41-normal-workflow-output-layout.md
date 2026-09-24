---
type: source
title: Bactopia v4.1 normal workflow output layout
status: insight
category: devops
created: 2026-09-16
updated: 2026-09-16
slug: bactopia-v41-normal-workflow-output-layout
---

# Bactopia v4.1 normal workflow output layout

Bactopia v4.1.0 with Nextflow 26.04.6 completed the normal ONT workflow on the resized m5.large EC2 launcher in 24m58s when run with `--skip_qc_plots true`. DATASETS, GATHER, QC, assembler, sketcher, Prokka, AMRFinderPlus, MLST, and merged reports completed; one assembler retry recovered.

The v4 output contract differs from v3.2 in important ways. V3 QC publishes `main/qc/<sample>.fastq.gz` and `main/qc/summary/*`; v4 publishes `main/qc/<sample>_ONT.fastq.gz` and `main/qc/supplemental/*`. V4 also publishes `main/sketcher`, `main/annotator/prokka`, and `tools/amrfinderplus`/`tools/mlst`. The v3 baseline was partial because its dataset process failed, but its core QC FASTQ and assembler outputs exist. Kraken2 v4 output paths and the report parser contract remain untested.

*Category: devops*

---
*Captured: 2026-09-16*

## Related

_Add links to related pages._
