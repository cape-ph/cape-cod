---
type: source
title: "Observation: Batch Kraken2 hangs during S3 sample directory enumeration"
tags:
  - aws
  - batch
  - nextflow
  - kraken2
  - s3
  - diagnosis
  - runtime-version
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-batch-kraken2-hangs-during-s3-sample-directory-enumeration
relevance: high
observed_at: 2026-09-14T16:11:00.664Z
source_context: Read-only diagnosis of hung Bactopia Kraken2 AWS Batch job
---

# ⭐ Observation: Batch Kraken2 hangs during S3 sample directory enumeration

Read-only diagnosis traced Batch job f91dc64c-076f-4011-8569-bee6e7cea4f8 to the Bactopia `collect_samples` function. CloudWatch stream `ccd-pvsl-nextflow-jobdef/default/09e45c816f964dbcacc4bbd0d8c3cbf4` stops after `Including 1 samples for analysis`; the next source operation is `file("${bactopia_dir}/").eachFile` at `~/.nextflow/assets/bactopia/bactopia/lib/nf/bactopia_tools.nf:38`, and `Found 1 samples to process` at line 60 never appears. No jobs were present in the analysis Batch queue, so the parent has not reached child-job submission. The Batch image runs Nextflow 25.10.4 with nf-amazon 3.4.4, while the working EC2 run uses Nextflow 24.04.4 with nf-amazon 2.5.3 against the same Bactopia v3.2.0 revision. Nextflow documentation indicates nf-amazon switches to AWS SDK v2 starting with Nextflow 25.10. The Batch host uses AMI ami-0ad4ff177982b3e5e in subnet-0179187d613306876; the working EC2 uses ami-0d244966929712cb6 in subnet-0abd0987d4acc22a4. Both use the same workflow instance profile and workflow security group. ECS Exec is disabled and the Batch instance is not SSM-registered, so direct in-container S3 testing was unavailable. Leading hypothesis: a Nextflow 25.10.4/nf-amazon S3 directory-listing regression or runtime difference, with Batch-vs-EC2 network path still not fully excluded. A secondary likely issue is the generated config's `aws.batch.cliPath = '/home/ec2-user/miniconda/bin/aws'`, although the kickstart image installs AWS CLI via pip and does not create that path.

*Relevance: high*
*Context: Read-only diagnosis of hung Bactopia Kraken2 AWS Batch job*
*Tags: aws batch nextflow kraken2 s3 diagnosis runtime-version*

---
*Observed: 2026-09-14T16:11:00.664Z*
