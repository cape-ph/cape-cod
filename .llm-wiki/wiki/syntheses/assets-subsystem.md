---
type: synthesis
title: "Assets Subsystem (assets/)"
slug: assets-subsystem
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["assets", "etl", "lambda", "runtime-code", "capepy", "subsystem"]
---

# Assets Subsystem (`assets/`)

`assets/` holds runtime code and configuration that the Pulumi program deploys
into AWS - it is NOT part of the Pulumi program itself. The Pulumi constructs
upload these files to S3, bake them into Lambda functions / Glue jobs /
container images, or render them as templates at deploy time.

## Important provenance caveat

`assets/README.md` states plainly: "DO NOT MANAGE ALL ASSETS HERE LONG TERM."
Many files are here only to bootstrap the system and are expected to move to
their own repos with their own lifecycle/CI. Several are already mirrored from
source repos and must be manually kept in sync, e.g.:

- `etl/etl_gphl_cre_alert.py` <- `cape-ph/etl-gphl-cre-alert`
- `etl/etl_tnl_alert.py` <- `cape-ph/etl-tnl-alert`
- `etl/etl_gphl_sequencing_alert.py` <- `cape-ph/etl-gphl-sequencing-alert`

Treat many of these files as vendored copies: fixing a bug here may need to be
carried upstream, and vice versa.

## The `capepy` runtime SDK

Deployed Python code depends on the `capepy` package (a Lambda layer;
`assets/lambda-layers/capepy/capepy-3.0.0-...whl`, config `cape-cod:meta`
function layers). It provides the runtime abstractions the assets use:

- `capepy.aws.glue.EtlJob` - Glue ETL job context (source file access, params,
  logger, sink writes).
- `capepy.aws.dynamodb.EtlTable` / `PipelineTable` - registry table access.
- `capepy.aws.lambda_.BucketNotificationRecord` / `EtlRecord` - event parsing.
- `capepy.aws.meta.Boto3Object`, `capepy.aws.utils.decode_error`.

`capepy` is developed separately; `pyrightconfig.json` ignores `assets/etl/**`
for type checking because these run in the layer's environment, not the repo
venv. See [[concepts/coding-style-and-tooling]].

## Contents (per-file coverage)

- [[entities/assets-etl-scripts]] - Glue ETL scripts (`assets/etl/`).
- [[entities/assets-trigger-functions]] - S3 -> SQS and SQS -> Glue trigger
  Lambdas (`assets/trigger-functions/`).
- [[entities/assets-capi-handlers]] - CAPE API (capi) endpoint Lambda handlers
  (`assets/api/capi/handlers/`).
- [[entities/assets-api-authorizer-and-spec]] - API authorizer and the OpenAPI
  spec template (`assets/api/authz/`,
  `assets/api/capi/capi-openapi-301.yaml.j2`).
- [[entities/assets-analysis-pipelines]] - DAP fixtures
  (`assets/analysis-pipelines/`).
- [[entities/assets-containers]] - Nextflow kickstart container
  (`assets/containers/`).
- [[entities/assets-instance-user-data]] - EC2 bootstrap templates
  (`assets/instance/user-data/templates/`).
- [[entities/assets-report]] - canned report data + template (`assets/report/`).
- [[entities/assets-lambda-layers]] - Lambda layer build inputs
  (`assets/lambda-layers/`).

## How assets connect to the Pulumi program

- ETL scripts -> uploaded to a script bucket, run by `EtlJob` (see
  [[entities/pipeline-data-module]]).
- Trigger Lambdas -> wired by `Tributary.configure_sqs_lambda_target` /
  `configure_src_bucket_notifications` (see [[entities/datalake-module]]) and
  [[entities/queue-module]].
- capi handlers + authorizer + OpenAPI spec -> consumed by `CapeRestApi` (see
  [[entities/cape-rest-api-module]]).
- Analysis-pipeline fixtures -> loaded into DynamoDB by `DAPRegistry` (see
  [[entities/dap-registry-module]]).
- Container -> built by ECR and run by Batch (see [[entities/ecr-module]],
  [[entities/batch-module]]).
- User-data templates -> rendered for EC2 app instances (see
  [[entities/private-swimlane-module]]).
- Report -> canned reports (see [[entities/capemeta-module]]).

Related: [[syntheses/cape-cod-architecture-overview]].
