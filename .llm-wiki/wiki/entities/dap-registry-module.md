---
type: entity
title: "pipeline/registry module (DAPRegistry, WorkflowMetaRegistry)"
slug: dap-registry-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["registry", "dynamodb", "analysis-pipelines", "workflows", "pipeline"]
---

# pipeline/registry module (`capeinfra/pipeline/registry.py`)

Two DynamoDB-backed registries.

## `DAPRegistry(CapeComponentResource)`

Registry of Data Analysis Pipelines (DAPs).

- `type_name` = `capeinfra:pipeline:DAPRegistry`.
- `default_config`: `pipelines` (path to the analysis-pipeline fixtures dir,
  default `./assets/analysis-pipelines`).
- `DAP_FIXTURE = "dap-fixtures.json"`; `DEFAULT_NEXTFLOW_CONFIG` is a
  placeholder nextflow config (marked as currently unused).
- `create_dap_registry_table()` - creates an `aws.dynamodb.Table`
  (`PAY_PER_REQUEST`, hash key `pipeline_id`, GSI `PipelineNameVerIndex` on
  `pipeline_name`/`version`). NOTE: it ignores GSI changes
  (`ignore_changes=["global_secondary_indexes"]`) as a workaround for spurious
  server-side diffs - a known hack that would mask real GSI changes.
- `load_pipeline_assets()` - globs `**/*.json` under the pipelines dir, renders
  each as a Jinja template (passing `aws_region`; see
  [[entities/util-modules]]), and resolves pipeline `inherits` dependencies
  iteratively before writing each resolved profile as a `TableItem`. Inheritance
  is resolved by repeatedly processing profiles whose parents are already
  loaded; unresolved inheritances are logged and skipped.

The fixtures live in `assets/analysis-pipelines/` (e.g. bactopia variants; see
[[syntheses/assets-subsystem]]). The registry is queried by the DAP API handlers
(see [[entities/cape-rest-api-module]]).

## `WorkflowMetaRegistry(CapeComponentResource)`

- `type_name` = `capeinfra:meta:capemeta:WorkflowMetaRegistry`.
- `default_config` = `{}` (nothing configurable yet).
- `create_workflow_meta_store()` - creates a `DynamoTable` (see
  [[entities/database-module]]) keyed on `dag_id`, mapping an Airflow workflow
  (DAG) to the DAP@version entries it uses. Workflows themselves are deployed
  outside Pulumi (cape-cod-env ansible repo); this only creates the metadata
  store.

Related: [[syntheses/pipeline-subsystem]], [[entities/airflow-module]],
[[concepts/capepulumi-base-classes]].
