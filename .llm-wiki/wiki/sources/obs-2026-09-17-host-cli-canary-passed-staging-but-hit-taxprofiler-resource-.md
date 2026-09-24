---
type: source
title: "Observation: Host CLI canary passed staging but hit taxprofiler resource ceiling"
tags:
  - taxprofiler
  - aws
  - batch
  - cliPath
  - s3
  - staging
  - kraken2
  - resource
  - sizing
  - EFS
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-host-cli-canary-passed-staging-but-hit-taxprofiler-resource-
relevance: critical
observed_at: 2026-09-17T19:47:17.151Z
source_context: "Issue #379 host-CLI path canary"
---

# 🔴 Observation: Host CLI canary passed staging but hit taxprofiler resource ceiling

The canary against the deployed awsbatch AMI with aws.batch.cliPath=/home/ec2-user/miniconda/bin/aws passed the child runtime and staging boundary. Taxprofiler UNTAR completed successfully for the S3 database archive, and FASTQC completed successfully; this proves the safe host CLI path fixes the /usr collision and that S3 sheet/database-archive staging works mechanically. The Kraken2 child was created with 12 vCPU and 73728 MiB from the upstream process_high label and remained RUNNABLE with MISCONFIGURATION:JOB_RESOURCE_REQUIREMENT because the current analysis Batch compute environment cannot meet that request. The parent was terminated after recording the result. No actual Kraken2 database or EFS mount was used in this canary.

*Relevance: critical*
*Context: Issue #379 host-CLI path canary*
*Tags: taxprofiler aws batch cliPath s3 staging kraken2 resource sizing EFS*

---
*Observed: 2026-09-17T19:47:17.151Z*
