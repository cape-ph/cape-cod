---
type: entity
title: "pipeline/batch module (BatchCompute, BatchJobDefinition)"
slug: batch-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["batch", "compute", "ec2", "pipeline"]
---

# pipeline/batch module (`capeinfra/pipeline/batch.py`)

AWS Batch constructs for running containerized analysis jobs.

## `BatchJobDefinition(CapeComponentResource)`

- `type_name` = `capeinfra:datalake:BatchJobDefinition`.
- Constructor: `BatchJobDefinition(name, properties, repository, **kwargs)` -
  creates an `aws.batch.JobDefinition` of type `container`. If
  `properties["image"]` names an image in the given `ContainerRepository`, the
  job's `container_properties` are resolved (via `Output.apply`) to the built
  image URI; otherwise `properties` are used as-is. Registers `job_definition`
  as an output.

## `BatchCompute(CapeComponentResource)`

- `type_name` = `capeinfra:datalake:BatchCompute`.
- `default_config`: `resources.instance_types` (default `["c4.large"]`) and
  `resources.max_vcpus` (default 16).
- Constructor: `BatchCompute(name, vpc, subnets, **kwargs)` - creates a MANAGED
  EC2 compute environment plus a `JobQueue`. Also builds:
  - a Batch service role (`AWSBatchServiceRole` managed policy),
  - an instance role + instance profile. NOTE: the instance role currently
      gets broad managed policies (`AmazonS3FullAccess`, `AWSBatchFullAccess`,
      `AmazonElasticFileSystemClientFullAccess`) as a placeholder pending a real
      scoped policy (ISSUE #73),
  - a security group (no inbound, all outbound - to be tightened, ISSUE #77),
  - a cluster placement group.
  - Job queue priority 5; fair-share scheduling policy is stubbed out (ISSUE
      #78). EC2 key pair is commented out (ISSUE #77).

Container images come from [[entities/ecr-module]]. Airflow is granted access to
these compute environments and job definitions (see
[[entities/airflow-module]]). Instantiated via
`ScopedSwimlane.create_batch_compute_environments` / `create_job_definitions`
(see [[entities/scoped-swimlane-module]]).

Related: [[syntheses/pipeline-subsystem]], [[entities/iam-module]],
[[concepts/capepulumi-base-classes]].
