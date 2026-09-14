---
type: source
title: "Observation: Nextflow 26.04.6 resolves the production prefix collision"
tags:
  - aws
  - batch
  - nextflow
  - "2604"
  - s3
  - prefix
  - collision
  - confirmed
  - fix
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-nextflow-26-04-6-resolves-the-production-prefix-collision
relevance: critical
observed_at: 2026-09-14T17:06:36.624Z
source_context: Final Nextflow 26.04.6 runtime canary
---

# 🔴 Observation: Nextflow 26.04.6 resolves the production prefix collision

The final corrected Batch canary `8562a704-ac92-4479-9f58-c6ff8444e0b3` downloaded and actually ran Nextflow 26.04.6 build 12646 with nf-amazon 3.9.2 on the same Batch host and current image environment. Against the original `pipeline-output/` root, it completed `isDirectory()` for `micah-test` despite sibling prefixes `micah-test-2`, `micah-test-3`, and `micah-test-4`, completed the `kraken-debug-0` sample and QC existence checks, and logged `NEXTFLOW_2604_METADATA_COMPLETED`. Nextflow 25.10.4/nf-amazon 3.4.4 hangs at the same `micah-test` check. This validates the upstream Nextflow S3 lookup fix as the remediation for the prefix collision. The Batch image has not been updated yet; the test downloaded 26.04.6 only into the temporary container filesystem.

*Relevance: critical*
*Context: Final Nextflow 26.04.6 runtime canary*
*Tags: aws batch nextflow 2604 s3 prefix collision confirmed fix*

---
*Observed: 2026-09-14T17:06:36.624Z*
