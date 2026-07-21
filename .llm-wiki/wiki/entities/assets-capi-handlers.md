---
type: entity
title: "assets: capi API handlers (assets/api/capi/handlers/)"
slug: assets-capi-handlers
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["api", "lambda", "handlers", "capi", "assets"]
---

# assets: capi API handlers (`assets/api/capi/handlers/`)

The Lambda handlers backing the CAPE API (capi). Each is a small module with an
`index_handler(event, context)` entry point, wired to an API Gateway route by
the rendered OpenAPI spec and created as a Lambda by `CapeRestApi` (see
[[entities/cape-rest-api-module]], [[entities/assets-api-authorizer-and-spec]]).

## Common pattern

- Use `capepy` helpers (`capepy.aws.dynamodb.PipelineTable`/`EtlTable`,
  `capepy.aws.utils.decode_error`) and `boto3` clients.
- Return `{statusCode, headers, body}` with `body` JSON-encoded; errors decode
  `ClientError` and return 500.
- Handlers set permissive CORS headers (`Access-Control-Allow-Origin: *`). This
  is a deliberate temporary bypass flagged as ISSUE #141 - not wanted long term;
  intended to be replaced once API and web share a domain or CORS origins become
  configurable via Lambda env vars.

## Object / bucket handlers

- `get_raw_objstores.py` - list available raw object stores (buckets).
- `get_bucket_crawler.py` - crawler info for a bucket.
- `get_object_etls.py` - ETLs applicable to a given object.
- `get_raw_obj_post_url.py` - presigned POST URL for uploading a raw object.
- `get_mpu_part_urls.py` - presigned multipart-upload part URLs.
- `get_s3_contents.py` - listing of S3 contents.

## Data analysis pipeline (DAP) handlers

- `get_daps.py` - GET all pipelines; scans `PipelineTable` (with pagination) and
  returns `pipeline_name`, `pipeline_type`, `project`, `version` per item.
- `get_dap_profile.py` - a single pipeline's profile.
- `get_dap_status.py` - status of a DAP run.
- `get_dap_logs.py` - logs for a DAP run.
- `submit_dap_run.py` - POST a new DAP run; submits an AWS Batch job
  (`batch_client.submit_job`) with a Nextflow job definition, passing pipeline
  project/version/options as container env overrides. NOTE: currently uses
  hardcoded queue/job-definition names (e.g. `ccd-pvsl-...`) with a TODO to move
  them to env vars.

## Airflow workflow handlers

- `get_workflow_dags.py` - available Airflow DAGs.
- `get_workflow_pipeline_profiles.py` - DAP profiles used by a workflow.
- `get_workflow_run.py` - a specific workflow run.
- `get_workflow_runs.py` - the calling user's workflow runs. Lists recent runs
  across all DAGs via Airflow's cross-DAG endpoint `GET /dags/~/dagRuns/list`
  (paged), and returns only those whose `conf.cape.triggering_user_id` matches
  the caller (resolved from the API authorizer context; see
  [[analyses/workflow-user-attribution]]).
- `get_workflow_run_task_instances.py` - task instances for a run.
- `get_workflow_tasks.py` - tasks for a workflow.
- `post_workflow_run.py` - create a workflow run. Stamps the triggering user
  onto the DAG run `conf` under `conf.cape` (`triggering_user_id` /
  `triggering_user_name`) from the authorizer context, strips any
  client-supplied `cape` (anti-spoofing), and sets a `Triggered by <user>`
  run note. See [[analyses/workflow-user-attribution]].
- `patch_workflow_run.py` - update a workflow run.

## User attribute handlers

- `get_user_attributes.py` - all attributes for a user.
- `get_user_attribute_val.py` - a specific user attribute value.

## Report handler

- `get_canned_report.py` (largest, ~386 lines) - retrieves/generates a canned
  report; related to the report assets (see [[entities/assets-report]]).

Related: [[syntheses/assets-subsystem]], [[entities/cape-rest-api-module]],
[[entities/dap-registry-module]].
