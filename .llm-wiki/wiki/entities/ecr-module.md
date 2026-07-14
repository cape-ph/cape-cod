---
type: entity
title: "pipeline/ecr module (ContainerRepository, ContainerImage)"
slug: ecr-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["ecr", "containers", "docker", "pipeline"]
---

# pipeline/ecr module (`capeinfra/pipeline/ecr.py`)

ECR wrappers built on `pulumi_awsx`.

## `ContainerRepository(CapeComponentResource)`

- `type_name` = `capeinfra:datalake:ContainerRepository`.
- Constructor: `ContainerRepository(name, **kwargs)` - creates an
  `awsx.ecr.Repository` (named `<name>-repo`) and keeps a dict of
  `ContainerImage`s. Registers `repository_url` as an output.
- `add_image(name, config)` - builds and registers a `ContainerImage` into the
  repo, keyed by `name` (used by `BatchJobDefinition` image resolution, see
  [[entities/batch-module]]).

## `ContainerImage(CapeComponentResource)`

- `type_name` = `capeinfra:datalake:ContainerImage`.
- Constructor: `ContainerImage(name, repository, **kwargs)` - builds an
  `awsx.ecr.Image` (Docker build) pushed to the repository URL; `**self.config`
  supplies build args. Registers `container_image_uri` as an output.

Container build contexts live in `assets/containers/` (e.g.
`nextflow-kickstart/`; see [[syntheses/assets-subsystem]]). Images are consumed
by AWS Batch job definitions (see [[entities/batch-module]]).

Related: [[syntheses/pipeline-subsystem]], [[concepts/capepulumi-base-classes]].
