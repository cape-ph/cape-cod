---
type: source
title: "Notify-queue Phase 2b: datalake.py wiring + CapeConfig list-item gotcha"
slug: notify-queue-phase2-datalake-wiring-capeconfig-list-gotcha
status: insight
created: 2026-08-05
updated: 2026-08-05
category: architecture
---
# Notify-queue Phase 2b: datalake.py wiring + CapeConfig list-item gotcha
Completed the second half of the config-driven S3->SQS notification feature (Phase 2b) building on the already-landed queue.py/lambda pure-function work from [[sources/obs-2026-08-05-phase-2-notify-queue-feature-added-to-sqsqueue-and-s3-notifi]].

capeinfra/datalake/datalake.py (Tributary class):
- __init__ now parses optional `self.notify_cfgs` from `pipelines.data.notify` config and creates `self.notify_queue` (SQSQueue named f"{self.name}-ntfq") only when notify config is present. IMPORTANT GOTCHA: CapeConfig.get() (capepulumi.py) only wraps Mapping results in CapeConfig - list results come back as plain dicts. Calling `.get("key", default=...)` (keyword form) on those plain dict list items raises `TypeError: dict.get() takes no keyword arguments` at runtime (only caught by actually running pytest against the real dev stack config, not by static analysis). Fix: wrap each list entry explicitly, e.g. `self.notify_cfgs = [CapeConfig(ncfg) for ncfg in self.config.get("pipelines", "data", "notify", default=[])]`. The existing configure_etl() sidesteps this because it re-wraps `cfg` inside EtlJob's own CapeComponentResource.__init__ (config=cfg kwarg), so `job.config.get(...)` works - but any NEW code iterating a raw config list directly needs the same explicit CapeConfig() wrap per item.
- configure_src_bucket_notifications extended additively: role gets a conditional notify-queue put_msg statement, Lambda env gets conditional NOTIFY_QUEUE_NAME/TRIBUTARY_NAME/NOTIFY_RULES (built via Output.all(**{src: bucket.id}) keyed by physical bucket name, since that's what S3 events carry), and the permission/notification loop iterates `self.sources | set(notify_srcs)` so notify-only buckets (e.g. input-clean with no ETL) also get wired. When notify config is absent, notify_srcs=[] so this is byte-identical to the pre-feature code (verified: existing hai/genomics tributaries get zero behavioral diff).
- Preserved exact Pulumi logical resource names throughout (role, lambda, per-source permission/notification, existing ETL queue) to avoid forcing replacement of the shared deployed notifier.

Pulumi.cape-cod-dev.yaml: added `notify: [{name: split-reads, src: input-clean, prefix: sequencing-reads-split, message_retention_seconds: 43200}]` under seqauto's pipelines.data, plus schema doc comments and a WARNING about self-triggering loops (watching a prefix the same pipeline writes into).

tests/test_notifier_lambda.py (new): unit tests for match_notify_rules/build_notify_message loaded via importlib.util.spec_from_file_location (matches tests/test_workflow_user_attribution.py convention for single-file Lambdas), with AWS_DEFAULT_REGION set before import since the module calls boto3.client("sqs") at import time.

Known pre-existing test failures unrelated to this work (confirmed via git stash before/after): tests/test_capemeta.py::test_asset_bucket and tests/test_datalake.py::test_catalog both fail on a real unmocked `boto3` S3 GetObject NoSuchBucket during catalog bucket construction - needs AWS creds/network, not fixable without touching unrelated code. This also means the mock_datalake fixture (which builds a full DatalakeHouse from the real dev stack config) can never be used to assert notify-wiring identity without first fixing that gap; left a NOTE comment in tests/test_datalake.py explaining this and pointing at `pulumi preview` for identity verification instead of forcing a fragile mock-based test.
*Category: architecture*
---
*Captured: 2026-08-05*
## Related
_Add links to related pages._