---
type: analysis
title: "Workflow user attribution (conf.cape)"
slug: workflow-user-attribution
status: stable
confidence: high
created: 2026-07-20
updated: 2026-07-21
tags: ["api", "airflow", "mwaa", "workflows", "authorizer", "security", "capi"]
---

# Workflow user attribution (`conf.cape`)

How the capi API records "which user triggered an Airflow DAG run" and exposes a
per-user run list, given the MWAA integration constraints. See
[[entities/assets-capi-handlers]] and [[entities/assets-api-authorizer-and-spec]]
for the code, and [[entities/airflow-module]] / [[entities/cape-rest-api-module]]
for the surrounding infrastructure.

## Constraint

The capi Lambdas reach Airflow through `mwaa_client.invoke_rest_api`, which is
authenticated to MWAA by the shared API Lambda IAM role (a single service
principal) - not as the end user. Airflow therefore cannot populate its native
`triggering_user_name` with the Cognito user; it would only ever see the service
identity. Faithfully setting the native field would require presenting each end
user's identity to Airflow's auth manager, a large change to the auth model.

## Why not authenticate the real user into Airflow?

A natural question is whether we could pass the Cognito bearer token through to
Airflow so it authenticates as the actual user (and populates its native
triggering-user field). On MWAA this is not achievable:

- MWAA's Airflow web/REST auth is AWS IAM-based (access is granted via
  `mwaa:CreateWebLoginToken` / `airflow:InvokeRestApi`), not our Cognito user
  pool. MWAA does not let you swap the Airflow auth backend to an OIDC/Cognito
  provider, and nothing in `capeinfra/pipeline/airflow.py` wires one up.
- The frontend never talks to Airflow directly. It calls the capi API
  (API Gateway -> Lambda), and the Lambda reaches Airflow with
  `mwaa_client.invoke_rest_api`, authenticated by SigV4 using the Lambda
  execution role (mapped to the Airflow `Op` role in `private.py`). The Cognito
  token is consumed and discarded at the API Gateway edge and never travels to
  Airflow, so Airflow only ever sees that single service principal.
- Getting a true per-user Airflow identity would require self-managed Airflow
  (not MWAA) with a Cognito OIDC auth backend, plus the frontend hitting Airflow
  directly or the API impersonating the user via token passthrough - a large
  infra shift that abandons MWAA's managed benefits.

So resolving identity at the Cognito-authenticated API edge and stamping it into
`conf.cape` is the correct pattern under the MWAA constraint, not a workaround
for a missing feature.

## Decision

Record the user in the DAG run `conf` under a namespaced `cape` block, which is
persisted in Airflow state, shown in the Airflow UI, and returned by the Airflow
REST API - with no database dependency.

- `conf.cape = { triggering_user_id, triggering_user_name }`. The id is the
  stable Cognito `sub` (used for filtering); the name is email/username (for
  human-readable display).
- Identity is resolved server-side, never trusted from the client.

## Flow

1. `authz/default_apigw_authorizer.py` decodes the `Authorization` bearer token
   and injects `triggering_user_id` / `triggering_user_name` into the authorizer
   `context`. (Signature verification is still TODO - see the authorizer page.)
2. `handlers/post_workflow_run.py` reads that context via
   `caller_identity_from_event`, then `apply_cape_identity` strips any
   client-supplied `conf.cape` (anti-spoofing) and stamps the resolved identity.
   It also sets the DAG run `note` to `Triggered by <user>` so admins see the
   owner in the Airflow runs list without opening `conf`.
3. `handlers/get_workflow_runs.py` (route `GET /workflows/runs`, handler key
   `get_workflow_runs_handler`) resolves the caller (`caller_user_id`, with a
   `userId` query-string fallback for pre-authorizer/dev calls), lists each
   DAG's recent runs, and returns only those where
   `conf.cape.triggering_user_id` matches (`filter_runs_for_user`).

## IAM / wiring notes

- The new handler shares the API Lambda role, which already gets MWAA
  `invoke_rest_api` permission via the managed policy attachment from
  `MwaaEnvironment` (see `capeinfra/swimlanes/private.py`), so no IAM change was
  needed. `MWAA_ENVIRONMENT` is injected into all capi handlers via the shared
  `env_vars` in `capeinfra/resources/api.py`.
- Registered in `Pulumi.cape-cod-dev.yaml` and `Pulumi.cape-cod-public.yaml`
  and in `capi-openapi-301.yaml.j2` (with the standard OPTIONS CORS mock).

## Follow-ups / risks

- Authorizer does not verify the JWT signature yet; harden before production or
  switch to a native API Gateway Cognito User Pools authorizer (AWS handles
  verification/JWKS; handlers would then read `requestContext.authorizer.claims`).
  This migration is fully specified in cape-ph/cape-cod#352.
- Per-user listing filters in the proxy because Airflow has no server-side
  filter on a `conf` value (true in every Airflow version). Runs are fetched via
  Airflow 3's cross-DAG list endpoint `GET /dags/~/dagRuns/list` (the `~`
  wildcard covers all DAGs), paged at 100 up to a scan cap, so it is one
  paginated stream rather than one request per DAG. Large run volumes may still
  warrant a database-backed ownership index (the CAPE environment DB) later;
  this scalability follow-up is fully specified in cape-ph/cape-frontend#30.

Related: [[syntheses/assets-subsystem]], [[concepts/coding-style-and-tooling]].
