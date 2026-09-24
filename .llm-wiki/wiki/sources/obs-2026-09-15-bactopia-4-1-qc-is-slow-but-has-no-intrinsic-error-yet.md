---
type: source
title: "Observation: Bactopia 4.1 QC is slow but has no intrinsic error yet"
tags:
  - bactopia
  - v4
  - qc
  - nanoplot
  - ec2
  - batch
  - resume
status: observation
created: 2026-09-15
updated: 2026-09-15
slug: obs-2026-09-15-bactopia-4-1-qc-is-slow-but-has-no-intrinsic-error-yet
relevance: high
observed_at: 2026-09-15T18:26:43.509Z
source_context: Bactopia v4.1 EC2 QC work-directory diagnosis
---

# ⭐ Observation: Bactopia 4.1 QC is slow but has no intrinsic error yet

The Bactopia v4.1 EC2 retry with Docker profile and S3 cache completed DATASETS and GATHER, then QC child job `c570c615-e7d1-4825-aab7-2f9d055af8e2` ran for roughly 85 minutes on `quay.io/biocontainers/bactopia-qc:1.0.4--hdfd78af_0` with 4 vCPU and 8 GB RAM. It was killed by Nextflow when the bounded 90-minute SSH run ended, with exit code 143 and no intrinsic QC error. The persisted work log contains original NanoPlot outputs and stops after `Skipping coverage reduction`; final QC outputs were not produced. The safe continuation is `-resume` from the same v4.1 work directory with a longer bound, rather than restarting DATASETS/GATHER.

*Relevance: high*
*Context: Bactopia v4.1 EC2 QC work-directory diagnosis*
*Tags: bactopia v4 qc nanoplot ec2 batch resume*

---
*Observed: 2026-09-15T18:26:43.509Z*
