---
type: analysis
title: Nextflow Batch runtime and EFS staging decision aid
slug: nextflow-batch-runtime-and-efs-staging
status: historical
created: 2026-09-18
updated: 2026-09-23
tags:
  - nextflow
  - aws-batch
  - efs
  - taxprofiler
  - runtime
---

# Nextflow on AWS Batch: host and database access

This is a historical decision aid retained in the PR 385 wiki. The user-facing
EFS capability contract is documented in `extra-doc/README.efs-batch.md`; this
page preserves runtime and staging evidence and is not a deployment runbook.

This document describes the CAPE runtime contract for running Nextflow data
analysis pipelines on AWS Batch. It is written for pipeline integrators and
operators who need to connect a Nextflow workflow to CAPE's Batch environment.
It is not a guide to writing Nextflow processes.

The relevant AMI source repository is:

<https://github.com/cape-ph/aws-batch-ecs-ami>

The repository builds several different AMI profiles. The active profile must
be identified from the deployed Batch compute environment and AMI metadata. Do
not infer the active profile from a filename alone. The current CAPE Batch
compute environment uses the `awsbatch` profile. The repository also contains
other profiles, including a historical `nextflow-kraken2` profile, but that
profile is not the current Batch AMI contract unless the deployed AMI is checked
and confirms it.

## Parent and child runtime boundaries

CAPE starts a Nextflow parent job in the kickstart container. Nextflow then
submits individual process jobs to the AWS Batch analysis queue.

These are separate runtime boundaries:

- The parent container contains Nextflow, the AWS CLI, and the generated
  Nextflow configuration.
- Each child process runs in its own pipeline container on an AWS Batch host.
- A mount on the parent container does not automatically appear in a dynamic
  child job.
- A host path mounted into a child container is a path on the Batch EC2 host,
  not a path that exists only in the parent image.

The parent AWS CLI path and the host AWS CLI path are also separate:

```text
Parent container:
  command -v aws

Batch host:
  /home/ec2-user/miniconda/bin/aws
```

The parent path is used by the kickstart entrypoint for operations such as
creating a temporary work bucket. The host path is used by Nextflow's
`aws.batch.cliPath` setting when child jobs stage files from S3.

Do not set `aws.batch.cliPath` to the result of `command -v aws` inside the
parent container unless that path is also a valid path on every Batch host.

## AWS CLI path and child mounts

Nextflow's AWS Batch executor treats `aws.batch.cliPath` as the path to the AWS
CLI on the host AMI. It mounts the grandparent directory of that path into the
child container at the same path.

For example:

```groovy
aws.batch.cliPath = '/home/ec2-user/miniconda/bin/aws'
```

causes the host directory `/home/ec2-user/miniconda` to be mounted into the
child container at `/home/ec2-user/miniconda`.

A path under `/usr` is unsafe when the child image uses `/usr/local`. Mounting
the host `/usr` directory can hide files that the child image needs, including:

```text
/usr/local/env-execute
/usr/local/bin/_entrypoint.sh
```

The current `awsbatch` AMI installs a self-contained AWS CLI under
`/home/ec2-user/miniconda/bin/aws`, which avoids that collision. The directory
must exist on every replacement Batch host, not only on one currently running
instance.

Nextflow documentation recommends Wave and Fusion for modern S3 staging. If
the classic AWS CLI staging path remains in use, the host AMI CLI path must be
explicitly maintained and tested.

## Database access option 1: host-mounted EFS

In this model, every analysis Batch EC2 host mounts the shared EFS filesystem
before it accepts work. Nextflow continues using a host-path volume mapping:

```groovy
aws.batch.volumes =
    '/mnt/nextflow_shared_data:/mnt/nextflow_shared_data:ro'
```

The database sheet uses the stable child path:

```csv
tool,db_name,db_params,db_type,db_path
kraken2,cape-kraken2-ont,,long,/mnt/nextflow_shared_data/kraken2
```

The implementation has these parts:

- The `awsbatch` AMI or its instance bootstrap installs the EFS client tools.
- The Batch host mounts the configured EFS filesystem at
  `/mnt/nextflow_shared_data`.
- The mount is established before the ECS agent accepts Batch work, or the
  host is treated as unhealthy when the mount cannot be established.
- EFS mount targets exist in every Availability Zone used by the analysis
  compute environment.
- The EFS security group permits NFS traffic from the Batch host security
  group.
- The instance role has the required EFS client permissions.
- The child volume mapping is read-only.
- The database directory is versioned or otherwise protected from writes by
  analysis processes.

The filesystem identifier should come from deployment or runtime configuration.
It should not be embedded in a generic AMI or a DAP fixture.

Mount design choices include:

- Mount during host bootstrap versus a systemd mount unit. A systemd unit with
  network readiness and ECS ordering gives a clear host-readiness boundary.
- EFS IAM authorization and TLS versus network-only mounting. IAM plus TLS is
  the safer production choice.
- Mount the filesystem root versus an EFS access point. An access point can
  provide a narrower root and consistent permissions.
- Mount EFS on every analysis host versus use a dedicated database-capable Batch
  compute environment.
- Store one shared database version versus versioned directories with an
  explicit current version.
- Use the existing EFS throughput configuration versus tune provisioned
  throughput after measuring concurrent Kraken2 reads.

Advantages:

- The approximately 8 GiB database is not transferred for every run.
- Larger future databases avoid repeated S3 download time and transfer cost.
- Multiple child jobs can reuse the persistent database.
- The model matches the existing Nextflow host-path volume behavior.

Risks:

- Every replacement Batch host must mount EFS correctly.
- EFS latency and throughput affect Kraken2 performance.
- A missing mount can look like an empty database unless host readiness and
  child visibility are tested explicitly.
- An AMI or bootstrap rollout is required before production use.

## Database access option 2: ECS-managed EFS on each child

In this model, each dynamic child Batch job receives an ECS-managed EFS volume
in its own container properties. The host does not need to mount EFS at the
shared path.

The child job shape would contain an EFS volume configuration similar to:

```text
volume:
  name: kraken_database
  efsVolumeConfiguration:
    fileSystemId: resolved at runtime
    rootDirectory: /kraken2
    transitEncryption: ENABLED
    authorizationConfig:
      accessPointId: resolved at runtime

mountPoint:
  sourceVolume: kraken_database
  containerPath: /mnt/nextflow_shared_data/kraken2
  readOnly: true
```

The implementation has these parts:

- A way for the Nextflow AWS Batch executor to add
  `efsVolumeConfiguration` to dynamically submitted child jobs.
- Runtime resolution of the filesystem, access point, mount targets, IAM role,
  and security-group configuration.
- IAM permissions for the Batch task and any role used to submit or run it.
- Tests that inspect the actual child job definition and verify EFS visibility.
- A stable mapping from a CAPE database selector to the child mount contract.

The current Nextflow `aws.batch.volumes` setting does not create an
ECS-managed EFS volume. It creates a Docker host-path volume. Implementing this
option would therefore require one of the following:

- Extend or fork the Nextflow AWS Batch executor to support an EFS-specific
  volume configuration.
- Contribute a generalized EFS volume feature upstream to Nextflow.
- Add a CAPE-owned task submission layer that constructs the required Batch
  child job shape.
- Use pre-created job definitions for selected processes. This is less generic
  and does not fit the normal dynamic Nextflow task model well.
- Use a different Batch compute model, such as Fargate with EFS, while still
  solving the dynamic task configuration problem.

Advantages:

- Child storage is explicit in the AWS Batch task definition.
- Host AMI mount state is not a dependency.
- Replacement Batch hosts do not need a database mount.
- The storage relationship is easier to isolate per child workload.

Risks:

- The current Nextflow runtime does not provide this behavior through the
  existing host-path setting.
- A forked executor or CAPE-owned submission path creates a significant
  maintenance boundary.
- IAM, EFS network, task-definition, and cross-AZ behavior require a larger
  platform test matrix.
- The implementation must remain generic enough for future taxprofiler tools,
  not only Kraken2.

## Current validation evidence

The CAPE taxprofiler canaries established these facts:

- S3-hosted taxprofiler input and database sheets are accepted by taxprofiler
  2.0.1 under Nextflow 26.04.6.
- The parent kickstart container can see the current EFS database.
- The current `awsbatch` host CLI path allows child S3 staging and prevents the
  `/usr` mount collision.
- A temporary Kraken2 resource override of 4 vCPU and 16 GiB allows the child
  to schedule on the current analysis compute environment.
- The parent ECS-managed EFS mount is not propagated to dynamic child jobs.
- Adding `/mnt/nextflow_shared_data` to `aws.batch.volumes` does not attach the
  parent's ECS-managed EFS to a child. It only requests a host-path mount.
- No real Kraken2 classification has yet been run through the taxprofiler
  route with the EFS database.

The first production-oriented implementation should therefore prefer option 1
unless the team explicitly accepts the larger Nextflow executor/platform lift
required by option 2. S3 database staging should remain an evaluated fallback,
not the default assumption.

## Validation requirements

Before either option is treated as production-ready, record:

- The deployed AMI source profile and host CLI path.
- The Batch queue and compute environment used by the child.
- The requested and actual child CPU and memory.
- The child instance type and Availability Zone.
- The database path, mount type, and visible database files.
- EFS mount target and security-group behavior.
- S3 bytes transferred for sheets, input reads, database files, and outputs.
- Child and parent CloudWatch log streams.
- Kraken2 report shape and semantic comparison with the established baseline.
- No orphaned Batch jobs after success or bounded failure.

Do not put account-specific resource IDs in DAP fixtures or generic runtime
configuration. Resolve them from deployment outputs, runtime context, or a
versioned platform registry.
