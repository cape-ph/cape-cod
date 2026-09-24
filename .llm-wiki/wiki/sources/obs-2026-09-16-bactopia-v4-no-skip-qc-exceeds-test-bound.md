---
type: source
title: "Observation: Bactopia v4 no-skip QC exceeds test bound"
tags:
  - bactopia
  - qc
  - aws
  - batch
  - nanoplot
  - migration
status: observation
created: 2026-09-16
updated: 2026-09-16
slug: obs-2026-09-16-bactopia-v4-no-skip-qc-exceeds-test-bound
relevance: high
observed_at: 2026-09-16T20:12:57.549Z
source_context: Post-resize Bactopia v4.1 no-skip QC validation
---

# ⭐ Observation: Bactopia v4 no-skip QC exceeds test bound

A post-resize Bactopia v4.1.0 no-skip QC resume on EC2 instance i-01274bddc155993e8 (m5.large) ran for 1h54m44s before the bounded parent timeout stopped it. AWS Batch QC job d11ca863-0b4f-479a-a565-c8d3411a4b96 requested 4 vCPU and 8192 MiB, remained running until Nextflow terminated it, exited 143 with status reason `Job killed by NF`, and produced original NanoPlot artifacts but no final QC output. The launcher remained healthy with about 7.1 GiB available, no new kernel OOM evidence, and no orphaned Batch jobs afterward. The resize improved launcher stability but did not establish acceptable default QC runtime; the likely remaining decision is higher child resources, a longer bound, or an intentional skip-plots policy. Findings are recorded in .llm-wiki/wiki/analyses/kraken2-and-bactopia-41-migration-findings.md.

*Relevance: high*
*Context: Post-resize Bactopia v4.1 no-skip QC validation*
*Tags: bactopia qc aws batch nanoplot migration*

---
*Observed: 2026-09-16T20:12:57.549Z*
