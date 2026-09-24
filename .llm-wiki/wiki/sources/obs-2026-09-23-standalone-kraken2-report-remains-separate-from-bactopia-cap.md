---
type: source
title: "Observation: Standalone Kraken2 report remains separate from Bactopia CAPI report"
tags:
  - issue-379
  - taxprofiler
  - kraken2
  - report
  - bactopia
  - capi
  - separation
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-standalone-kraken2-report-remains-separate-from-bactopia-cap
relevance: high
observed_at: 2026-09-23T20:12:01.019Z
source_context: Clarification of report paths during controlled fixture planning
---

# ⭐ Observation: Standalone Kraken2 report remains separate from Bactopia CAPI report

The taxprofiler Kraken2 child already produces a standalone `*.kraken2.report.txt` artifact. The v4 report was compared semantically against the v3 baseline: same row count and taxid set, with documented rank-code and low-count ordering differences. The existing Bactopia single-sample CAPI data function does not query taxprofiler output, so the remaining synthetic sample fixture should validate only the `input_meta` to Bactopia metadata/AMR/species report join. Kraken2 should remain a separate report/artifact path unless a later requirement explicitly adds it to the CAPE Cod CAPI report.

*Relevance: high*
*Context: Clarification of report paths during controlled fixture planning*
*Tags: issue-379 taxprofiler kraken2 report bactopia capi separation*

---
*Observed: 2026-09-23T20:12:01.019Z*
