---
type: source
title: "Observation: Glue ETL job role missing S3 read on capepy wheel (data.py EtlJob) - blocks job launch, second refactor casualty"
slug: obs-2026-08-05-glue-etl-job-role-missing-s3-read-on-capepy-wheel-data-py-et
status: observation
created: 2026-08-05
updated: 2026-08-05
relevance: high
observed_at: 2026-08-05T16:44:37.064Z
tags: ["etl", "glue", "iam", "capepy", "wheel", "s3", "permissions", "refactor", "phase1"]
source_context: "Post-deploy ETL retest: notifier fix worked, Glue job role missing capepy wheel read"
---
# ⭐ Observation: Glue ETL job role missing S3 read on capepy wheel (data.py EtlJob) - blocks job launch, second refactor casualty
After the notifier DDB-table-name fix deployed, the seqauto ETL trigger chain now works end-to-end up to the Glue job LAUNCH, confirming that fix. New blocker surfaced: the Glue ETL job role fails at launch with S3 403 downloading the capepy wheel:

`User: .../ccd-dlh-T-seqauto-ETL-seqreadarch-role-808014e/GlueJobRunnerSession is not authorized to perform: s3:GetObject on resource: arn:aws:s3:::ccd-meta-assets-vbkt-s3-8b7134e/capepy-3.0.0-py3-none-any.whl`

Root cause (same late-2025 refactor casualty): in `capeinfra/pipeline/data.py`, the `EtlJob.etl_role` grants S3 read on the script bucket scoped ONLY to `{arn}/{self.config['script']}` (the ETL script object). But the Glue job also downloads the capepy wheel at launch via `--additional-python-modules` (`default_arguments=capeinfra.meta.capepy.uri.apply(add_to_python_modules)`), and that wheel object (`capepy-3.0.0-py3-none-any.whl` at the meta-assets bucket root) is NOT in the grant. The capepy-as-additional-python-modules wiring landed 2025-12-05 (commit 4b814903, Micah) without expanding the role grant.

Fix applied (uncommitted, gated): added a statement to `EtlJob.etl_role` granting `script_bucket.policies[read]` on the capepy wheel object ARN, derived version-agnostically from `capeinfra.meta.capepy.uri.replace("s3://", "arn:aws:s3:::")`. `python -m py_compile capeinfra/pipeline/data.py` passes; diff is the single inserted block, no ruff churn.

Note: pi-lens flagged a false-positive "L268 __init__ should not return a value" - that `return default_args` is inside the nested `add_to_python_modules` closure (def at line 262), not `__init__` (line 168); valid Python, pre-existing, untouched.

Retest note: the prior S3 event was already consumed (notifier enqueued -> sqs lambda StartJobRun succeeded -> job failed at launch, no auto-retry), so after deploying this fix the object must be re-uploaded (or the Glue job manually re-run) to re-trigger. This bug affects all tributaries' ETL jobs, not just seqauto. See [[sources/etl-notifier-ddb-table-name-mismatch]].
*Relevance: high*

*Context: Post-deploy ETL retest: notifier fix worked, Glue job role missing capepy wheel read*

*Tags: etl glue iam capepy wheel s3 permissions refactor phase1*
---
*Observed: 2026-08-05T16:44:37.064Z*