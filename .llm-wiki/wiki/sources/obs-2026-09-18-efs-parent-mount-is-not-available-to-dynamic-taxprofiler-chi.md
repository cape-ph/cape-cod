---
type: source
title: "Observation: EFS parent mount is not available to dynamic taxprofiler children"
tags:
  - taxprofiler
  - efs
  - aws
  - batch
  - child
  - mount
  - database
  - staging
  - bactopia
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-efs-parent-mount-is-not-available-to-dynamic-taxprofiler-chi
relevance: critical
observed_at: 2026-09-18T13:19:37.082Z
source_context: "Issue #379 EFS-path taxprofiler canary"
---

# 🔴 Observation: EFS parent mount is not available to dynamic taxprofiler children

The EFS-path taxprofiler canary used a database sheet with db_path=/mnt/nextflow_shared_data/kraken2, the current host CLI path, a temporary aws.batch.volumes host mapping, and the 4 vCPU / 16 GiB Kraken2 override. The parent kickstart container saw the real EFS database and listed hash.k2d (8000000032 bytes), opts.k2d, taxo.k2d, and supporting tax files. FASTQC completed in the child. The Kraken2 child reached the test beforeScript but reported EFS_KRAKEN2_SENTINEL_MISSING for hash.k2d/opts.k2d/taxo.k2d. This proves the parent ECS-managed EFS mount is not propagated to dynamically created child Batch jobs, and aws.batch.volumes is only a host-path mount. No S3 database staging or real classification occurred. The host-mounted EFS strategy therefore requires analysis-host EFS bootstrap/mounting or a separate managed-EFS child-job mechanism; do not assume the current parent volume is sufficient.

*Relevance: critical*
*Context: Issue #379 EFS-path taxprofiler canary*
*Tags: taxprofiler efs aws batch child mount database staging bactopia*

---
*Observed: 2026-09-18T13:19:37.082Z*
