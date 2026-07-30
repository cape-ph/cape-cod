---
type: entity
title: "assets: API authorizer and OpenAPI spec (assets/api/)"
slug: assets-api-authorizer-and-spec
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["api", "authorizer", "openapi", "security", "assets"]
---

# assets: API authorizer and OpenAPI spec (`assets/api/`)

## `authz/default_apigw_authorizer.py`

A Lambda request authorizer for API Gateway. It makes an allow-all access
decision (real allow/deny policy still TODO), but it now resolves the caller's
Cognito identity from the `Authorization` bearer token and passes it downstream
to endpoint handlers via the authorizer `context`:

- `get_bearer_token(headers)` extracts the token (case-insensitive header,
  tolerates a bare token with no `Bearer` prefix).
- `decode_jwt_claims(token)` base64url-decodes the JWT payload. IMPORTANT: it
  does NOT verify the signature yet (module TODO) - treat identity as
  authenticated-by-transport-only until signature verification or a managed
  Cognito JWT authorizer is added.
- `identity_context_from_claims(claims)` maps `sub` ->
  `triggering_user_id` and `email`/`cognito:username` -> `triggering_user_name`.
- `generate_policy(principalId, effect, resource, context=None)` returns the IAM
  policy plus the string-valued `context` map.

Handlers read that identity from `event.requestContext.authorizer` (e.g.
`post_workflow_run.py` stamps it into the DAG run `conf.cape`; `get_workflow_runs.py`
filters runs by it). See [[analyses/workflow-user-attribution]]. Anonymous/
unparseable tokens still get an allow with an empty context (rollout safety).
NOTE: the authorizer Lambda is created with no env vars; signature verification
would need Cognito config (JWKS/issuer) wired in.

Wired via `CapeRestApi._create_api_authorizer_lambdas` (see
[[entities/cape-rest-api-module]]).

## `capi/capi-openapi-301.yaml.j2`

The OpenAPI 3.0.1 specification for the capi API, as a Jinja2 template (~2100
lines). It is rendered at deploy time by `CapeRestApi._render_spec` (via
[[entities/util-modules]] `get_j2_template_from_path`) and used to create the
`aws.apigateway.RestApi`. The spec maps routes to the handler Lambdas in
[[entities/assets-capi-handlers]].

### How routes bind to handlers

Each path/method has an `x-amazon-apigateway-integration` block of
`type: aws_proxy` whose `uri` references a Jinja variable
`{{ handlers['<name>_handler'] }}`. `CapeRestApi` supplies the `handlers` dict
mapping each handler key to that Lambda's invoke ARN. Every path also defines an
`options` method backed by a `type: mock` integration that returns permissive
CORS headers (the ISSUE #141 bypass; see [[entities/assets-capi-handlers]]).

### Route -> handler key table

| Path                           | Handler key (spec)                        | Handler file                         |
| ------------------------------ | ----------------------------------------- | ------------------------------------ |
| `/rawobjstorage`               | `get_raw_objstore_authz_handler`          | `get_raw_objstores.py`               |
| `/objuploadurl`                | `get_raw_obj_upload_url_handler`          | `get_raw_obj_post_url.py`            |
| `/objstorage/contents`         | `get_s3_contents_handler`                 | `get_s3_contents.py`                 |
| `/objstorage/etls`             | `get_object_etls_handler`                 | `get_object_etls.py`                 |
| `/objstorage/crawler`          | `get_bucket_crawler_handler`              | `get_bucket_crawler.py`              |
| `/objstorage/parturls`         | `get_mpu_part_upload_urls_handler`        | `get_mpu_part_urls.py`               |
| `/user/attributes`             | `get_user_attributes_handler`             | `get_user_attributes.py`             |
| `/user/attribute`              | `get_user_attribute_val_handler`          | `get_user_attribute_val.py`          |
| `/report/create`               | `get_canned_report_handler`               | `get_canned_report.py`               |
| `/dap/pipelines`               | `get_daps_handler`                        | `get_daps.py`                        |
| `/dap/pipelineprofile`         | `get_dap_profile_handler`                 | `get_dap_profile.py`                 |
| `/dap/status`                  | `get_dap_status_handler`                  | `get_dap_status.py`                  |
| `/dap/logs`                    | `get_dap_logs_handler`                    | `get_dap_logs.py`                    |
| `/dap/submit`                  | `submit_dap_run_handler`                  | `submit_dap_run.py`                  |
| `/workflows`                   | `get_workflow_dags_handler`               | `get_workflow_dags.py`               |
| `/workflows/pipelineprofiles`  | `get_workflow_pipeline_profiles_handler`  | `get_workflow_pipeline_profiles.py`  |
| `/workflows/trigger`           | `post_workflow_run_handler`               | `post_workflow_run.py`               |
| `/workflows/halt`              | `patch_workflow_run_handler`              | `patch_workflow_run.py`              |
| `/workflows/run`               | `get_workflow_run_handler`                | `get_workflow_run.py`                |
| `/workflows/runs`              | `get_workflow_runs_handler`               | `get_workflow_runs.py`               |
| `/workflows/tasks`             | `get_workflow_tasks_handler`              | `get_workflow_tasks.py`              |
| `/workflows/run/taskinstances` | `get_workflow_run_task_instances_handler` | `get_workflow_run_task_instances.py` |

Note: the spec handler key names do not always match the file names (e.g.
`get_raw_objstore_authz_handler` -> `get_raw_objstores.py`); the binding of key
to file is set up in `CapeRestApi`.

Related: [[syntheses/assets-subsystem]], [[entities/cape-rest-api-module]].
