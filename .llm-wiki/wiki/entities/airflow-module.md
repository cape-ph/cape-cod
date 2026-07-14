---
type: entity
title: "pipeline/airflow module (MwaaEnvironment)"
slug: airflow-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["airflow", "mwaa", "orchestration", "pipeline"]
---

# pipeline/airflow module (`capeinfra/pipeline/airflow.py`)

## `MwaaEnvironment(CapeComponentResource)`

Managed Apache Airflow (Amazon MWAA) environment plus the IAM plumbing to let
Airflow drive AWS Batch.

- `type_name` = MWAA namespace; has a `PolicyEnum` and `default_config`.
- `base_role_policy_statements()` - the base execution-role policy statements
  for the MWAA environment.
- Constructor:
  `MwaaEnvironment(name, vpc, subnets, ingress_subnets, aws_region, aws_account_id, extra_policy_statements=None, **kwargs)` -
  creates the MWAA environment in the given VPC/subnets with an execution role.
- `policies` - IAM statement groups.
- `configure_batch_compute_pass_role(batch_compute_envs)` - grants the MWAA role
  pass-role access to Batch compute environment roles. A TODO notes it should
  probably target exactly one role/env.
- `configure_batch_job_def_policy(batch_job_defs)` - grants access to Batch job
  definitions (a TODO notes it is nearly identical to the compute-env case).

Instantiated by `PrivateSwimlane.create_airflow_compute_environment` (see
[[entities/private-swimlane-module]]). Airflow DAGs/workflows are deployed
outside Pulumi (cape-cod-env ansible repo); workflow metadata is tracked in
`WorkflowMetaRegistry` (see [[entities/dap-registry-module]]).

Related: [[syntheses/pipeline-subsystem]], [[entities/batch-module]],
[[entities/iam-module]], [[concepts/capepulumi-base-classes]].
