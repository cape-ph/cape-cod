---
type: source
title: "Observation: Next taxprofiler retry targets 2 vCPU and 9 to 10 GiB"
tags:
  - issue-379
  - taxprofiler
  - resource
  - sizing
  - retry
  - plan
status: observation
created: 2026-09-21
updated: 2026-09-21
slug: obs-2026-09-21-next-taxprofiler-retry-targets-2-vcpu-and-9-to-10-gib
relevance: high
observed_at: 2026-09-21T20:34:47.869Z
source_context: End-of-session handoff
---

# ⭐ Observation: Next taxprofiler retry targets 2 vCPU and 9 to 10 GiB

Tomorrow's direct taxprofiler retry should request 2 vCPUs and 9 to 10 GiB memory, starting at 9 GiB if nf-core/taxprofiler accepts it. Keep generation-3 queue `ccd-pvsl-taxonomic-profiling-g3-btch-jobq-a8f4880`, the explicit EFS host volume `/mnt/nextflow_shared_data:/mnt/nextflow_shared_data:ro`, and the normal Kraken2 `stageInMode = 'symlink'` rule. The current m5.xlarge pool remains unchanged; this is a direct-test override only. A later production instance-size change must account for the roughly 8 GiB Kraken2 database plus Kraken2 and ECS overhead. The stopped run's 8 GiB work bucket is preserved at `s3://nextflow-spot-batch-temp-acebda2c-33ac-4871-9270-862e710c263f/`.

*Relevance: high*
*Context: End-of-session handoff*
*Tags: issue-379 taxprofiler resource sizing retry plan*

---
*Observed: 2026-09-21T20:34:47.869Z*
