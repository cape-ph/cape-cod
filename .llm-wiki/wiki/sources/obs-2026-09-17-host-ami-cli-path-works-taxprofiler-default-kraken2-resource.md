---
type: source
title: "Observation: Host AMI CLI path works; taxprofiler default Kraken2 resources are unschedulable"
tags:
  - taxprofiler
  - aws
  - batch
  - ami
  - cliPath
  - resource
  - sizing
  - kraken2
  - EFS
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-host-ami-cli-path-works-taxprofiler-default-kraken2-resource
relevance: critical
observed_at: 2026-09-17T19:46:03.091Z
source_context: "Issue #379 host-CLI path canary"
---

# 🔴 Observation: Host AMI CLI path works; taxprofiler default Kraken2 resources are unschedulable

The host-AMI CLI canary used the existing analysis Batch environment and aws.batch.cliPath=/home/ec2-user/miniconda/bin/aws from the deployed awsbatch AMI. The Nextflow child jobs UNTAR and FASTQC completed successfully, confirming the safe host CLI mount avoids the /usr collision and child S3 staging works. The taxprofiler Kraken2 child was then created with 12 vCPU and 73728 MiB memory from nf-core/taxprofiler's process_high label. AWS Batch marked it unschedulable because the current analysis compute environment's largest configured c4.8xlarge has less memory. The canary was terminated after this resource finding; no database classification ran. A taxprofiler-specific Kraken2 process resource override is required before rerunning, and this is separate from the host AMI CLI fix.

*Relevance: critical*
*Context: Issue #379 host-CLI path canary*
*Tags: taxprofiler aws batch ami cliPath resource sizing kraken2 EFS*

---
*Observed: 2026-09-17T19:46:03.091Z*
