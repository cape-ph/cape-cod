---
type: synthesis
title: "CAPE Cod Architecture Overview"
slug: cape-cod-architecture-overview
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["architecture", "pulumi", "overview", "cape-cod"]
---

# CAPE Cod Architecture Overview

CAPE Cod is the Pulumi Infrastructure as Code (IaC) project for the Center for
Applied Pathogen Genomics (and Outbreak Control). It is a Python Pulumi program
that stands up an AWS environment: a data lake, data/analysis pipelines (ETL,
AWS Batch, Apache Airflow/MWAA), a private networked "swimlane" (VPC, subnets,
RDS, load balancers, EC2 app instances, VPN), REST APIs, and identity management
(Cognito). The whole system is early and actively changing; treat `README.md`
"features may change at any time" as literal.

## Entry points and control flow

Pulumi resolves the program from `Pulumi.yaml` (`runtime: python`,
`virtualenv: venv`). Pulumi executes `__main__.py`, which drives the entire
build in two moves:

1. `import capeinfra` runs `capeinfra/__init__.py` as an import side effect.
   That module computes the stack namespace and instantiates the two system-wide
   constructs at module scope:
    - `meta = CapeMeta(...)` - system-wide metadata/scaffolding (see
      [[entities/capemeta-module]]).
    - `data_lakehouse = DatalakeHouse(...)` - the data lake (see
      [[entities/datalake-module]]).
2. `__main__.py` then instantiates `PrivateSwimlane(...)` - the private
   networked environment (see [[entities/private-swimlane-module]]).

Because the top-level constructs are created as import side effects in
`capeinfra/__init__.py`, `capepulumi.py` is deliberately kept as a separate base
module with no top-level state - importing `capeinfra` anywhere would otherwise
cause circular import/instantiation problems. This is called out in the
`capepulumi.py` docstring and is a load-bearing design constraint. See
[[concepts/capepulumi-base-classes]].

## Stack namespacing

`capeinfra/__init__.py`:

- `CAPE_STACK_NS = pulumi.get_stack()` - the full stack name (e.g.
  `cape-cod-dev`).
- `stack_ns` - the first character of each hyphen-delimited word of the stack
  name (`cape-cod-dev` -> `ccd`). This exists because AWS resource names have
  very little room: roughly 56 characters after Pulumi appends a random 7-char
  suffix for uniqueness. The same length pressure is why `util/naming.py`
  provides `disemvowel`. See [[entities/util-modules]].

## Subsystem map

- Base layer - [[concepts/capepulumi-base-classes]]: `CapeComponentResource`
  (config-aware `pulumi.ComponentResource`), `CapeConfig` (deep-mergeable nested
  config dict), `update_dict`. Every CAPE construct subclasses
  `CapeComponentResource` and exposes `type_name`, `default_config`, and
  optionally `policies`.
- Meta - [[entities/capemeta-module]]: automation assets bucket, Lambda layers,
  `CapePy` (capepy layer), `CapePrincipals` (Cognito user/group/IdP/identity
  pool), `CapeCannedReports`.
- Data lake - [[entities/datalake-module]]: `DatalakeHouse`, `CatalogDatabase`
  (shared Glue catalog), and `Tributary` (a configurable data domain with
  raw/clean buckets, crawlers, ETL jobs, and SQS -> Lambda notification
  triggers).
- Swimlane - [[entities/scoped-swimlane-module]] and
  [[entities/private-swimlane-module]]: `ScopedSwimlane` (VPC/subnet/NAT/DNS/ALB
  scaffolding base) and `PrivateSwimlane` (the concrete private environment:
  RDS, MWAA, Batch, DAP registry, APIs, static web apps, EC2 instances, VPN).
- Pipeline - [[syntheses/pipeline-subsystem]]: `pipeline/data.py` (Glue
  `DataCrawler`, `EtlJob`), `pipeline/airflow.py` (`MwaaEnvironment`),
  `pipeline/batch.py` (`BatchCompute`, `BatchJobDefinition`), `pipeline/ecr.py`
  (`ContainerRepository`, `ContainerImage`), `pipeline/registry.py`
  (`DAPRegistry`, `WorkflowMetaRegistry`).
- Reusable resources - [[syntheses/resources-subsystem]]: `objectstorage.py`
  (`Bucket`, `VersionedBucket`), `database.py` (`DynamoTable`, `RDSInstance`),
  `api.py` (`CapeRestApi`), `compute.py` (Lambda layers + `CapeLambdaFunction`),
  `loadbalancer.py` (`AppLoadBalancer`), `queue.py` (`SQSQueue`), `certs.py`
  (`BYOCert`).
- IAM - [[entities/iam-module]]: policy/role helper functions shared across
  constructs.
- Util - [[entities/util-modules]]: `naming.py`, `jinja2.py`, `file.py`,
  `repo.py`.
- Deployed runtime code - [[syntheses/assets-subsystem]]: `assets/` holds code
  deployed into AWS (ETL Glue scripts, API Lambda handlers, container images,
  analysis-pipeline fixtures, EC2 user-data). This is not part of the Pulumi
  program itself and some of it is sourced from other repos.

## Configuration model

Everything is configuration-driven from the Pulumi stack config
(`Pulumi.cape-cod-dev.yaml` is the documented reference config;
`Pulumi.cape-cod-public.yaml` is the secret-scrubbed public mirror). Constructs
read nested config via `CapeConfig`. See [[concepts/pulumi-config-structure]].

## Testing and safety

Local verification is `pulumi preview` plus a small `pytest` suite using Pulumi
mocks. Agents must never run `pulumi up` - deployment is the user's
responsibility against live infrastructure. See
[[concepts/testing-and-pulumi-preview-workflow]].

## Tooling and style

Python is formatted with black + isort (line length 80); YAML/JSON/Markdown with
Prettier; type-checked with Pyright (basic). No ruff/flake8/biome enforcement.
See [[concepts/coding-style-and-tooling]].

## Where to start

New to this repo? Begin with the [[concepts/agent-playbook]] - the task loop,
hard rules, subsystem map, and known landmines in one place.
