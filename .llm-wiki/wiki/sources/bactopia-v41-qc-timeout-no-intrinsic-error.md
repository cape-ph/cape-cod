---
type: source
title: Bactopia v4.1 QC timeout without intrinsic error
status: insight
category: devops
created: 2026-09-15
updated: 2026-09-15
slug: bactopia-v41-qc-timeout-no-intrinsic-error
---

# Bactopia v4.1 QC timeout without intrinsic error

Bactopia v4.1 on the EC2 test instance successfully completed DATASETS and GATHER with the Docker profile and S3 cache prefix. QC child Batch job `c570c615-e7d1-4825-aab7-2f9d055af8e2` ran for roughly 85 minutes using `quay.io/biocontainers/bactopia-qc:1.0.4--hdfd78af_0`, 4 vCPU, and 8 GB RAM. It exited 143 because Nextflow killed it when the bounded 90-minute SSH run ended. The QC work log contains original NanoPlot outputs and `Skipping error correction` / `Skipping coverage reduction`, but no error; final QC output was not produced. The correct continuation is a `-resume` run against the same v4.1 work directory with a longer bound, not a complete restart.

*Category: devops*

---
*Captured: 2026-09-15*

## Related

_Add links to related pages._
