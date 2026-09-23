---
type: source
title: "Observation: EC2 launcher resources differ from Batch QC resources"
tags:
  - bactopia
  - qc
  - aws
  - batch
  - ec2
  - resources
  - nanoplot
status: observation
created: 2026-09-16
updated: 2026-09-16
slug: obs-2026-09-16-ec2-launcher-resources-differ-from-batch-qc-resources
relevance: high
observed_at: 2026-09-16T13:23:49.444Z
source_context: Bactopia v4.1 QC runtime diagnosis
---

# ⭐ Observation: EC2 launcher resources differ from Batch QC resources

The EC2 t3.micro OOM/reachability problem was addressed by resizing it to m5.large, but Bactopia QC computation runs in an AWS Batch child container, not on the EC2 launcher. The v4.1 QC child was configured with 4 vCPU and 8 GiB memory and ran about 85 minutes before the parent SSH timeout killed it. Therefore, more EC2 memory fixes launcher stability but does not increase QC child resources. The next v4 resume should still test `--skip_qc_plots`; if QC remains slow, compare the QC child resource request and consider a targeted higher-resource QC config or plot-only isolation.

*Relevance: high*
*Context: Bactopia v4.1 QC runtime diagnosis*
*Tags: bactopia qc aws batch ec2 resources nanoplot*

---
*Observed: 2026-09-16T13:23:49.444Z*
