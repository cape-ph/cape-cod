---
type: source
title: Nextflow 25.10.4 S3 listing hang in Kraken2 Batch
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: nextflow-25104-s3-directory-listing-kraken2-batch-hang
---

# Nextflow 25.10.4 S3 listing hang in Kraken2 Batch

Read-only diagnosis of AWS Batch job `f91dc64c-076f-4011-8569-bee6e7cea4f8` found a precise boundary in the Bactopia v3.2.0 source. The CloudWatch stream `ccd-pvsl-nextflow-jobdef/default/09e45c816f964dbcacc4bbd0d8c3cbf4` ends after `Including 1 samples for analysis`; `lib/nf/bactopia_tools.nf` then calls `file("${bactopia_dir}/").eachFile` at line 38 to enumerate the S3-backed Bactopia output, and the following `Found 1 samples to process` at line 60 never appears. No child analysis Batch jobs existed, proving the parent is blocked before Kraken2 task submission.

The working EC2 run uses Nextflow 24.04.4 and nf-amazon 2.5.3. The Batch kickstart image uses Nextflow 25.10.4 and nf-amazon 3.4.4, while both runs use Bactopia revision `4b075af96d` for `v3.2.0`. Nextflow documentation states that nf-amazon changes to AWS SDK v2 starting with Nextflow 25.10. The Batch compute host also uses `ami-0ad4ff177982b3e5e`, while the manually created working EC2 host uses `ami-0d244966929712cb6`; both share the workflow instance profile and primary security group. AWS CLI S3 listing from the working EC2 host returned 24 immediate sample prefixes in about one second. ECS Exec was disabled and the Batch instance was not SSM-registered, so direct execution inside the hung container was not available.

Leading diagnosis: a Nextflow 25.10.4/nf-amazon S3 filesystem directory-listing regression or compatibility issue, not failure to read the include object. The Batch-versus-EC2 subnet/NAT path remains an untested alternative. Before any code or infrastructure change, the next safe test should compare this exact Bactopia listing operation under the old and new Nextflow runtimes, or enable a temporary approved diagnostic path for the Batch container. Also verify the generated `aws.batch.cliPath` before child submission: it points to `/home/ec2-user/miniconda/bin/aws`, but the kickstart Dockerfile installs AWS CLI with pip and does not create Miniconda.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
