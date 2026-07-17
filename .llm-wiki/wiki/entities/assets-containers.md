---
type: entity
title: "assets: containers (assets/containers/)"
slug: assets-containers
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["containers", "docker", "nextflow", "batch", "assets"]
---

# assets: containers (`assets/containers/`)

Container build contexts built into ECR images (see [[entities/ecr-module]]) and
run as AWS Batch jobs (see [[entities/batch-module]]).

## `nextflow-kickstart/`

A "kickstart" container that runs a Nextflow pipeline on AWS Batch.

### `Dockerfile`

- Base `amazoncorretto:21.0.8`; installs Nextflow (`NXF_VER=25.10.4`), git,
  python-pip, curl, jq, and the AWS CLI. Increases yum timeout (deploy-dependent
  timeout issues noted). Declares a `/scratch` volume and runs `entrypoint.sh`.

### `entrypoint.sh`

- Reads env vars `PIPELINE_URL`, `PIPELINE`, `PIPELINE_VERSION`,
  `PIPELINE_QUEUE`, `NF_OPTS`. Determines the AWS region from ECS task metadata
  if unset.
- Fetches the pipeline into `/scratch`: S3 (`aws s3 cp --recursive`) for `s3://`
  URLs, otherwise `git clone`; empty scratch if no URL.
- Creates a temporary S3 work bucket (`nextflow-spot-batch-temp-<jobid>`),
  writes a `nextflow.config` (executor `awsbatch`, queue, a Kraken2
  `stageInMode = symlink` workaround marked to move to pipeline-specific
  config), runs `nextflow run`, then deletes the temp bucket.
- TODOs: allow a user-supplied nextflow config string; reconsider the
  `BACTOPIA_CACHEDIR` env var.

Related: [[syntheses/assets-subsystem]], [[entities/batch-module]],
[[entities/ecr-module]], [[entities/assets-analysis-pipelines]].
