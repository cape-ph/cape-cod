---
type: source
title: "Observation: DDB row verified correct [tar,gz]/unprocessed - trigger failure narrowed to S3 notification wiring or invocation"
slug: obs-2026-08-04-ddb-row-verified-correct-tar-gz-unprocessed-trigger-failure-
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T20:51:40.699Z
tags: ["seqauto", "etl", "s3-notification", "troubleshooting", "deploy", "glue"]
source_context: "Phase 1 testing: DDB verified correct, diagnosis narrowed to notification wiring / invocation"
---
# ⭐ Observation: DDB row verified correct [tar,gz]/unprocessed - trigger failure narrowed to S3 notification wiring or invocation
Follow-up to the direct-dump-didn't-fire issue: user verified the deployed ETLAttrs DynamoDB row is correct - prefix `unprocessed`, suffixes `[tar, gz]`. This eliminates the "stale DDB missing gz" theory. Combined with the repo config being correct (no S3-level filter, notifier suffix `.tar.gz` -> `gz` which is in the row), the notifier WOULD enqueue if it were invoked.

So the diagnosis narrows to everything OTHER than config/DDB. Highest-priority checks for next session, in order: (1) Does the input-raw bucket actually have the `BucketNotification` wired to the notifier Lambda? `aws s3api get-bucket-notification-configuration --bucket <seqauto-input-raw>` - empty/missing = drift or never deployed, the leading hypothesis now. (2) Notifier `*-lmbdtrgfnct` CloudWatch logs around upload time - no invocation confirms the notification isn't firing; an invocation that logs "ignored"/exception points elsewhere. (3) Confirm objects landed directly under `unprocessed/` in the real src bucket. (4) Downstream: ETL FIFO queue metrics, SQS-trigger Lambda logs, Glue run history. User will deploy and retest tomorrow AM; a deploy would re-assert the bucket notification if it had drifted.
*Relevance: high*

*Context: Phase 1 testing: DDB verified correct, diagnosis narrowed to notification wiring / invocation*

*Tags: seqauto etl s3-notification troubleshooting deploy glue*
---
*Observed: 2026-08-04T20:51:40.699Z*