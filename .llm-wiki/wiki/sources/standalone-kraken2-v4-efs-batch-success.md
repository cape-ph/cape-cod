---
type: source
title: Standalone Kraken2 v4 EFS Batch success
status: insight
category: devops
created: 2026-09-16
updated: 2026-09-16
slug: standalone-kraken2-v4-efs-batch-success
---

# Standalone Kraken2 v4 EFS Batch success

Temporary Batch job `c64f18e7-e055-42f4-8849-eb47d9c01a75` used an explicit ECS-managed EFS volume and the `bactopia-teton:1.1.4` image. It saw the shared EFS database (`hash.k2d`, about 7.5 GiB) and the Bactopia v4.1 ONT QC FASTQ. `k2 classify` completed in 2.913 seconds, processed 17,563 sequences, classified 17,562, and left 1 unclassified. The report had 360 lines with the same head and tail as the v3.2 Kraken2 baseline. This validates standalone Kraken2 execution for the v4.1 output and isolates the remaining problem to the Bactopia v4 tool wrapper and child host-path EFS behavior. The report was not persisted beyond the container yet; exact diff and temporary job-definition cleanup remain.

*Category: devops*

---
*Captured: 2026-09-16*

## Related

_Add links to related pages._
