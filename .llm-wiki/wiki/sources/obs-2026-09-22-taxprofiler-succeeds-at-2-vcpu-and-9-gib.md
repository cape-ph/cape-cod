---
type: source
title: "Observation: Taxprofiler succeeds at 2 vCPU and 9 GiB"
tags:
  - issue-379
  - taxprofiler
  - kraken2
  - aws
  - batch
  - efs
  - resource
  - sizing
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-taxprofiler-succeeds-at-2-vcpu-and-9-gib
relevance: critical
observed_at: 2026-09-22T13:38:37.708Z
source_context: Corrected direct taxprofiler retry
---

# 🔴 Observation: Taxprofiler succeeds at 2 vCPU and 9 GiB

The corrected direct nf-core/taxprofiler v2.0.1 retry succeeded on generation 3 after applying the trusted `.*KRAKEN2_KRAKEN2.*` selector. Parent job `3ca9a5c6-48e2-4f38-928a-ecd369ba40fa` and dynamic Kraken2 child `c4271264-892e-456f-82b7-c574326c3101` completed with exit code 0. The child requested 2 vCPUs and 9,216 MiB, mounted `/home/ec2-user/miniconda` and `/mnt/nextflow_shared_data`, and reported peak RSS about 7.1 GiB and peak virtual memory about 7.5 GiB. The synthetic one-read Kraken2 report was valid and showed 100 percent unclassified. Output is under `s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/taxprofiler-direct-g3-2vcpu-9gb-20260922132845/`. The temporary Nextflow work bucket contains about 8 GiB of staged database artifacts, so resource/runtime plumbing passed but zero-copy EFS staging economics remain to be investigated.

*Relevance: critical*
*Context: Corrected direct taxprofiler retry*
*Tags: issue-379 taxprofiler kraken2 aws batch efs resource sizing*

---
*Observed: 2026-09-22T13:38:37.708Z*
