---
type: source
title: "Observation: Implemented workflow user attribution via Airflow conf.cape (authorizer + capi handlers)"
slug: obs-2026-07-20-implemented-workflow-user-attribution-conf-cape
status: observation
created: 2026-07-20
updated: 2026-07-20
relevance: high
observed_at: 2026-07-20T00:00:00.000Z
tags: ["airflow", "mwaa", "workflows", "authorizer", "capi", "security", "cape-cod", "implemented"]
source_context: "Implementing per-user workflow run attribution across cape-cod + cape-frontend"
---
# Observation: Implemented workflow user attribution via Airflow conf.cape (authorizer + capi handlers)

Implemented server-side per-user attribution for Airflow DAG runs in cape-cod. Because capi reaches MWAA via mwaa_client.invoke_rest_api authenticated by the single shared API Lambda IAM role, Airflow's native triggering_user_name can't reflect the Cognito user; recorded the user in DAG run conf.cape = {triggering_user_id (Cognito sub), triggering_user_name (email/username)} instead (persisted in Airflow state, visible in UI, returned by REST API, no DB dependency). Changes: (1) assets/api/authz/default_apigw_authorizer.py - now decodes the Authorization bearer JWT (get_bearer_token, decode_jwt_claims, identity_context_from_claims: sub->triggering_user_id, email/cognito:username->triggering_user_name) and injects identity into the authorizer context; still allow-all and NO JWT signature verification yet (TODO: verify vs Cognito JWKS or switch to managed Cognito JWT authorizer; authorizer Lambda currently has no env vars). (2) assets/api/capi/handlers/post_workflow_run.py - caller_identity_from_event reads requestContext.authorizer; apply_cape_identity strips client-supplied conf.cape (anti-spoof) and stamps resolved identity; also sets run note "Triggered by <user>". (3) NEW assets/api/capi/handlers/get_workflow_runs.py - GET /workflows/runs, handler key get_workflow_runs_handler; caller_user_id (authorizer + userId qsp fallback), iterates /dags then /dags/{id}/dagRuns (limit 100, order_by -logical_date), filters by conf.cape.triggering_user_id (run_belongs_to_user/filter_runs_for_user), returns {dag_runs, total_entries}; 401 when caller unresolved. (4) capi-openapi-301.yaml.j2 - added /workflows/runs GET + OPTIONS CORS mock. (5) Pulumi.cape-cod-dev.yaml + Pulumi.cape-cod-public.yaml - registered get_workflow_runs_handler (capi-all layer, index.index_handler, py3.10). No IAM change needed: shared API role already has MWAA invoke via MwaaEnvironment managed policy attachment (private.py); MWAA_ENVIRONMENT injected via shared env_vars (resources/api.py). Tests: tests/test_workflow_user_attribution.py - 34 pass (loads single-file lambdas via importlib). Follow-up risks: JWT signature not verified; N+1 DAG iteration paged at 100 (large volumes may need DB-backed ownership index in CAPE env DB). Frontend (cape-frontend) sends the bearer token and consumes GET /workflows/runs, replacing cookie-based tracking.
*Relevance: high*
