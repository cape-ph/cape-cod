---
type: source
title: "Observation: Bactopia v3.2 Kraken2 baseline succeeds"
tags:
  - bactopia
  - v3
  - kraken2
  - baseline
  - ec2
  - report
status: observation
created: 2026-09-16
updated: 2026-09-16
slug: obs-2026-09-16-bactopia-v3-2-kraken2-baseline-succeeds
relevance: critical
observed_at: 2026-09-16T14:21:22.172Z
source_context: Bactopia v3.2.0 Kraken2 baseline run
---

# 🔴 Observation: Bactopia v3.2 Kraken2 baseline succeeds

The Bactopia v3.2.0 Kraken2 baseline on the EC2 instance succeeded in 9m23s using Nextflow 24.04.4 and the EC2-compatible `/home/ec2-user/miniconda/bin/aws` child mount. It found one included sample, submitted and completed the Kraken2 child job, and produced a report at `batch_job_scratch/bactopia41-ec2-20260915143928/v3.2.0-kraken/bactopia/caerbannog-test-nf2404-bt320/tools/kraken2/caerbannog-test-nf2404-bt320.kraken2.report.txt`. The report starts with standard Kraken2 six-column rows, including unclassified and root/cellular organism taxonomy. Run-level reports were also produced. This is the baseline to compare against Bactopia v4.1.

*Relevance: critical*
*Context: Bactopia v3.2.0 Kraken2 baseline run*
*Tags: bactopia v3 kraken2 baseline ec2 report*

---
*Observed: 2026-09-16T14:21:22.172Z*
