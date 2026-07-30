---
type: source
title: "Observation: Trigger path now gates on resolvable caller identity (401), matching list path"
slug: obs-2026-07-30-trigger-path-now-gates-on-resolvable-caller-identity-401-mat
status: observation
created: 2026-07-30
updated: 2026-07-30
relevance: high
observed_at: 2026-07-30T17:21:51.616Z
tags: ["cape-cod", "api", "auth", "airflow", "attribution", "pr-353"]
source_context: "PR #353 review response - workflow-run attribution auth gating"
---
# ⭐ Observation: Trigger path now gates on resolvable caller identity (401), matching list path
In cape-cod PR #353 (branch airflow_user_info), addressed a review from thecaffiend about asymmetric auth enforcement. Previously POST /workflows/trigger (assets/api/capi/handlers/post_workflow_run.py) triggered DAGs even with no resolvable identity (run just went unattributed), while GET /workflows/runs 401s. Fixed by gating the trigger: index_handler now resolves identity via caller_identity_from_event and returns 401 with CORS headers when triggering_user_id is absent, before calling MWAA. Response headers were hoisted into a shared resp_headers reused by the 401 and success returns. Also removed the earlier userId query-string fallback from get_workflow_runs.caller_user_id (spoofing risk). Added handler tests (monkeypatching post_workflow_run.boto3.client) asserting 401-without-identity never calls MWAA and stamp-then-trigger works with an identity; suite now 38 tests. Caveat: authorizer is still decode-only (no JWT signature verification), so the gate only requires a decodable token carrying a sub, not a verified user; re-key off verified claims when the native Cognito authorizer (#352) lands - noted on that issue. Commit ff81e14 (amended, force-pushed).
*Relevance: high*

*Context: PR #353 review response - workflow-run attribution auth gating*

*Tags: cape-cod api auth airflow attribution pr-353*
---
*Observed: 2026-07-30T17:21:51.616Z*