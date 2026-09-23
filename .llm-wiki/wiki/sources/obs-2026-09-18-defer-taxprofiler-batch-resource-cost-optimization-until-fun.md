---
type: source
title: "Observation: Defer taxprofiler Batch resource cost optimization until functional path works"
tags:
  - taxprofiler
  - aws
  - batch
  - cost
  - optimization
  - resources
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-defer-taxprofiler-batch-resource-cost-optimization-until-fun
relevance: medium
observed_at: 2026-09-18T13:06:47.140Z
source_context: "Issue #379 deferred resource-sizing follow-up"
---

# 🔍 Observation: Defer taxprofiler Batch resource cost optimization until functional path works

After the taxprofiler path is functionally working, review requested versus actual vCPU and memory for each enabled process, especially KRAKEN2_KRAKEN2, FASTQC, UNTAR, and MultiQC. Replace broad process_high defaults with measured process-specific allocations where safe, compare runtime and failure/retry behavior, and estimate Batch/EFS costs. This is a deferred optimization gate, not part of the current EFS mount canary.

*Relevance: medium*
*Context: Issue #379 deferred resource-sizing follow-up*
*Tags: taxprofiler aws batch cost optimization resources*

---
*Observed: 2026-09-18T13:06:47.140Z*
