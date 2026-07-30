---
type: source
title: "Observation: pulumi preview --diff for airflow_user_info: 7 feature changes + 4 pre-existing drift"
slug: obs-2026-07-28-pulumi-preview-diff-for-airflow-user-info-7-feature-changes-
status: observation
created: 2026-07-28
updated: 2026-07-28
relevance: high
observed_at: 2026-07-28T14:30:32.019Z
tags: ["pulumi", "preview", "deploy", "cape-cod", "airflow-user-attribution", "capi"]
source_context: "Deploy verification for workflow user attribution (cape-cod airflow_user_info)"
---
# ⭐ Observation: pulumi preview --diff for airflow_user_info: 7 feature changes + 4 pre-existing drift
Ran `pulumi preview --diff -s cape-cod-dev` for branch airflow_user_info (workflow user attribution). 11 changes total: 2 create, 8 update, 1 replace, 460 unchanged. Split cleanly into two groups.

Feature changes (7, all trace to the branch):
- update lambda ccd-pvsl-capi-api-default-hndlr (code -> assets/api/authz/default_apigw_authorizer.py)
- update lambda ccd-pvsl-capi-api-postdagrun (code -> assets/api/capi/handlers/post_workflow_run.py)
- create lambda ccd-pvsl-capi-api-getdagruns (code -> assets/api/capi/handlers/get_workflow_runs.py; shares role ccd-pvsl-capi-api-lmbd-role, env includes MWAA_ENVIRONMENT=ccd-pvsl-airflow-env-mwaa-env, layer capi-all:7, python3.10)
- create lambda permission ccd-pvsl-capi-api-getdagruns-allowlmbd (API GW invoke)
- update apigateway restApi body (new /workflows/runs route); body renders as a whole-block change because the recomputed spec embeds the new lambda invoke ARN which is [unknown] until create - normal for aws_proxy specs, not a real deletion
- replace apigateway deployment (redeploy_on_openapi_spec_sha256_change trigger changed because spec sha256 changed)
- update apigateway stage (deployment ref follows the replace)

Pre-existing drift (4, NOT from this branch - git diff confirms branch only touches wiki, Pulumi config, authorizer, openapi spec, the two handlers, tests):
- update cognito IdentityProvider GTRI-SSO (providerDetails ActiveEncryptionCertificate + SLO/SSORedirectBindingURI recompute to [unknown])
- update docker-build Image nextflow_kickstart (contextHash change -> rebuild)
- update batch jobDefinition ccd-pvsl-nextflow-jobdef (containerProperties recompute, revision bump, follows image rebuild)
- update iam policy ccd-pvsl-nextflow-jobdef-pssrl-plcy (references new job-definition revision ARN)

Preview is read-only against the shared s3://cape-pulumi-state backend; ran with valid creds (account 767397883306). Deploy remains the user's step.
*Relevance: high*

*Context: Deploy verification for workflow user attribution (cape-cod airflow_user_info)*

*Tags: pulumi preview deploy cape-cod airflow-user-attribution capi*
---
*Observed: 2026-07-28T14:30:32.019Z*