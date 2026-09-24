---
type: source
title: "Observation: Twenty-minute retry reached with unmatched Kraken2 override selector"
tags:
  - issue-379
  - taxprofiler
  - resource
  - override
  - nextflow
  - selector
  - aws
  - batch
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-twenty-minute-retry-reached-with-unmatched-kraken2-override-
relevance: critical
observed_at: 2026-09-22T13:15:45.313Z
source_context: 20-minute direct retry threshold
---

# 🔴 Observation: Twenty-minute retry reached with unmatched Kraken2 override selector

The 2 vCPU / 9 GiB direct taxprofiler retry reached the 20-minute startup threshold and was stopped. The child did not test those resources: its actual AWS Batch request was 12 vCPUs and 73,728 MiB (72 GiB), with `MISCONFIGURATION:COMPUTE_ENVIRONMENT_MAX_RESOURCE`. The temporary direct config used `withName: '.*:KRAKEN2|KRAKEN2'`, which did not match the actual process name containing `KRAKEN2_KRAKEN2`. The trusted profile selector `.*KRAKEN2_KRAKEN2.*` must be used on the next retry, alongside the EFS volume mapping and `stageInMode = 'symlink'`. Therefore the 2 vCPU / 9 GiB resource target remains untested; do not re-evaluate it based on this failed attempt.

*Relevance: critical*
*Context: 20-minute direct retry threshold*
*Tags: issue-379 taxprofiler resource override nextflow selector aws batch*

---
*Observed: 2026-09-22T13:15:45.313Z*
