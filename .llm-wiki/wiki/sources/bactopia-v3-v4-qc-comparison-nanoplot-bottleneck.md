---
type: source
title: Bactopia v3 versus v4 QC comparison
status: insight
category: devops
created: 2026-09-15
updated: 2026-09-15
slug: bactopia-v3-v4-qc-comparison-nanoplot-bottleneck
---

# Bactopia v3 versus v4 QC comparison

Bactopia v3.2.0 and v4.1.0 QC source modules implement the same broad ONT phases: nanoq filtering, skip ONT error correction, skip coverage reduction when genome size is zero, pre/post fastq-scan, original/final NanoPlot, and final read checks. v4 refactors the module, publishes outputs through supplemental/process paths, and uses `bactopia-check-fastqs` instead of v3's `check-fastqs.py`, with controls including `skip_qc`, `skip_qc_plots`, and `skip_fastq_check`.

On the same concatenated 29,669-read ONT input, v3 QC child job `84c2018a-ca18-43d6-9b10-0d9025ef3173` succeeded in about 2.6 minutes. v4 QC child job `c570c615-e7d1-4825-aab7-2f9d055af8e2` ran about 85 minutes, produced original NanoPlot output, and was killed by the bounded parent run before final QC output. No intrinsic error was recorded. The next diagnostic is v4 `-resume` with `--skip_qc_plots` to isolate NanoPlot from the rest of QC.

*Category: devops*

---
*Captured: 2026-09-15*

## Related

_Add links to related pages._
