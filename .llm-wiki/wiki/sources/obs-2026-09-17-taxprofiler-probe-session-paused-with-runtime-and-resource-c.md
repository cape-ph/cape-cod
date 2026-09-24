---
type: source
title: "Observation: Taxprofiler probe session paused with runtime and resource contracts identified"
tags:
  - taxprofiler
  - bactopia
  - nextflow
  - aws
  - batch
  - cliPath
  - efs
  - resource
  - override
  - resume
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-taxprofiler-probe-session-paused-with-runtime-and-resource-c
relevance: critical
observed_at: 2026-09-17T20:02:23.655Z
source_context: "Issue #379 taxprofiler probe session"
---

# 🔴 Observation: Taxprofiler probe session paused with runtime and resource contracts identified

Resume notes for Issue #379 taxprofiler integration. Test scratch root: s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/taxprofiler-sheet-probe-20260917185925/. Direct S3 input and database sheet paths were accepted by nf-core/taxprofiler 2.0.1 under Nextflow 26.04.6 after the ONT input row was corrected to include run_accession=probe-run. With the deployed generated cliPath=/usr/bin/aws, UNTAR and FASTQC children failed at container startup because Nextflow mounted host /usr over child /usr, hiding /usr/local/bin/_entrypoint.sh and /usr/local/env-execute. A no-cliPath canary removed that collision but failed child S3 staging with `aws: command not found`. The sibling AMI repo is https://github.com/cape-ph/aws-batch-ecs-ami; the deployed image ami-0ad4ff177982b3e5e is the awsbatch profile, not nextflow-kraken2, and commit ea3623e installs the host AWS CLI at /home/ec2-user/miniconda/bin/aws. A canary using that host path allowed UNTAR and FASTQC to complete and proved small S3 database-archive staging mechanically. Taxprofiler's default KRAKEN2_KRAKEN2 process requested 12 vCPU and 73728 MiB from process_high and was unschedulable on the current analysis compute environment. A temporary withName override to 4 vCPU, 16 GiB, and 4 hours allowed the full stub pipeline to complete successfully; the Kraken2 child exited 0 and published a stub report at resource-override-output/kraken2/cape-kraken2-ont/probe-sample_probe-run_cape-kraken2-ont.kraken2.kraken2.report.txt. The stub used a fake tiny database archive, so no real Kraken2 classification or EFS mount was tested. The current analysis CE instance types are c4.large, c4.xlarge, c4.2xlarge, c4.4xlarge, and c4.8xlarge; no resize was made. Temporary Nextflow work buckets from failed/successful probes remain untouched: nextflow-spot-batch-temp-898ebe80-104d-4d7a-9c26-08a751cc5cca, nextflow-spot-batch-temp-05a14f70-4ac6-4ac8-823e-dbd5dc4e6b2a, nextflow-spot-batch-temp-27c5b59c-388c-45a0-b827-b45848b7b3ea, nextflow-spot-batch-temp-fca602fd-e28f-44cd-89f6-0af3c56977af, and nextflow-spot-batch-temp-8e482d47-3bee-4be2-8b7b-6d23449ca5b4. Next session should first convert the temporary cliPath and KRAKEN2 resource overrides into an explicitly reviewed taxprofiler runtime contract, then run with the real EFS-backed database. Do not choose S3 database staging as the default without cost/performance analysis. User-facing extra-doc should cite the AMI GitHub URL, explain the awsbatch host/container contract, omit wiki references and manual-launcher debugging details, and avoid assuming the historical nextflow-kraken2 profile is current. No deploy, Pulumi change, commit, or scratch cleanup occurred during the probe session.

*Relevance: critical*
*Context: Issue #379 taxprofiler probe session*
*Tags: taxprofiler bactopia nextflow aws batch cliPath efs resource override resume*

---
*Observed: 2026-09-17T20:02:23.655Z*
