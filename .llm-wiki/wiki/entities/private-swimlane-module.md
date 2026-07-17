---
type: entity
title: "private swimlane (capeinfra/swimlanes/private.py)"
slug: private-swimlane-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["swimlane", "private", "vpc", "rds", "mwaa", "api", "vpn"]
---

# private swimlane (`capeinfra/swimlanes/private.py`)

`PrivateSwimlane` is the concrete private environment for CAPE and the last
thing `__main__.py` instantiates (see
[[syntheses/cape-cod-architecture-overview]]). It subclasses `ScopedSwimlane`
(see [[entities/scoped-swimlane-module]]) and is configured from
`cape-cod:swimlanes.private` (see [[concepts/pulumi-config-structure]]).

## Responsibilities

- `default_config` - the private swimlane's default configuration.
- `type_name` / `scope`.
- Constructor wires the whole environment together (VPC/subnets via the base,
  then the pieces below).

Environment pieces (methods):

- `create_env_rds_instance()` - the environment Postgres database via
  `RDSInstance` (see [[entities/database-module]]).
- `create_airflow_compute_environment()` - MWAA plus Batch access wiring via
  `MwaaEnvironment` (see [[entities/airflow-module]]).
- `create_analysis_pipeline_registry()` - `DAPRegistry`; and
  `create_workflow_meta_registry()` - `WorkflowMetaRegistry` (see
  [[entities/dap-registry-module]]).
- `_deploy_api(api_name)` - deploys a `CapeRestApi` (see
  [[entities/cape-rest-api-module]]); carries TODO ISSUE #61.
- Static web + APIs (several carry TODO ISSUE #176):
  `create_static_web_resources()`, `_deploy_static_app(sa_cfg)` (TODO ISSUE
  #126), `create_private_api_resources()`, `_create_app_alb()`,
  `_create_api_alb()` (using [[entities/loadbalancer-module]]).
- `create_application_instances()` - EC2 app instances;
  `_create_instance_profile` builds their instance profiles. Instance user-data
  templates live in `assets/instance/user-data/templates/` (see
  [[syntheses/assets-subsystem]]).
- `_create_hosted_domain()` - private hosted DNS/domain.
- `create_vpn()` - client VPN (TODO ISSUE #100, ISSUE #130); see
  `extra-doc/README.vpn.md`.

This class is the integration point that composes the meta, datalake, pipeline,
and resources subsystems into a running environment.

Related: [[syntheses/cape-cod-architecture-overview]],
[[entities/scoped-swimlane-module]], [[syntheses/pipeline-subsystem]],
[[syntheses/resources-subsystem]], [[syntheses/abac-opa-cross-repo]].
