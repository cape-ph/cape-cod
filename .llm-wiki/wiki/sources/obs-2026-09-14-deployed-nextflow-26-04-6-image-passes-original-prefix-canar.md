---
type: source
title: "Observation: Deployed Nextflow 26.04.6 image passes original prefix canary"
tags:
  - aws
  - batch
  - nextflow
  - deployed
  - validation
  - kraken2
  - s3
  - prefix
  - fix
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-deployed-nextflow-26-04-6-image-passes-original-prefix-canar
relevance: critical
observed_at: 2026-09-14T17:53:46.366Z
source_context: Post-deploy deployed-image metadata canary
---

# 🔴 Observation: Deployed Nextflow 26.04.6 image passes original prefix canary

Post-deploy verification found active `ccd-pvsl-nextflow-jobdef` revision 53 using ECR digest `sha256:e5b35a7c9f7fb06199fbfb2ed14ab67df420ec3412a4968668549321b54aa9a2`, pushed 2026-09-14. A deployed-image Batch canary `6a34132e-2665-4c9a-9f7e-db0c6909e2f8` ran Nextflow 26.04.6 build 12646 with nf-amazon 3.9.2 on the original `pipeline-output/` root. It completed `isDirectory()` for `micah-test` and all siblings, found `kraken-debug-0`, passed QC file metadata checks, and exited successfully without child jobs. The prefix collision fix is deployed and validated. The canary confirmed `/usr/bin/aws` exists but `/home/ec2-user/miniconda/bin/aws` remains absent, so child Batch submission still needs the separate CLI path fix before a full DAG run.

*Relevance: critical*
*Context: Post-deploy deployed-image metadata canary*
*Tags: aws batch nextflow deployed validation kraken2 s3 prefix fix*

---
*Observed: 2026-09-14T17:53:46.366Z*
