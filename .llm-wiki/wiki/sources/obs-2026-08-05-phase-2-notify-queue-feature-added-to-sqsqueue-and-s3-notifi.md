---
type: source
title: "Observation: Phase 2 notify-queue feature added to SQSQueue and S3 notifier lambda"
slug: obs-2026-08-05-phase-2-notify-queue-feature-added-to-sqsqueue-and-s3-notifi
status: observation
created: 2026-08-05
updated: 2026-08-05
relevance: high
observed_at: 2026-08-05T18:20:44.889Z
tags: ["sqs", "lambda", "s3-notifications", "queue.py", "phase2"]
source_context: "Phase 2 of config-driven S3->SQS notification feature, dispatched as a two-file Fixer task"
---
# ⭐ Observation: Phase 2 notify-queue feature added to SQSQueue and S3 notifier lambda
Implemented Phase 2 (config-driven S3->SQS notify path) across two files: capeinfra/resources/queue.py and assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py.

queue.py: SQSQueue.__init__ gained an optional message_retention_seconds: int | None = None kwarg, forwarded to aws.sqs.Queue only when not None (via a queue_kwargs dict built up before the Queue() call), so existing queues get no diff. SQS range is 60..1209600 seconds (14 days); default is 4 days.

new_s3obj_queue_notifier_lambda.py: kept the existing glue-etl path (env QUEUE_NAME, EtlTable, BucketNotificationRecord, static MessageGroupId f"{queue_name}-raw-data-msg") completely untouched. Added an additive notify path gated by three new env vars that are absent by default: NOTIFY_QUEUE_NAME, NOTIFY_RULES (JSON: {bucket: [{"name","prefix","suffixes"}]}), TRIBUTARY_NAME. Added pure functions match_notify_rules(bucket, key, rules) -> list[str] and build_notify_message(raw_record, bucket, key, tributary_name, notification) -> dict for unit testability without AWS, plus send_notify_message() mirroring send_etl_message()'s try/except style. Notify messages use MessageGroupId = the object key (per-object dedup/parallelism) instead of the ETL path's static group id. capepy's BucketNotificationRecord (capepy/aws/lambda_.py) only exposes .bucket and .key; eventTime/eventName/s3.object.size/s3.object.eTag must be read from the raw record dict directly.

Also learned: repo already had a pre-existing ruff-format violation in queue.py (the `def policies(self) -> dict[...]` multi-line return type) unrelated to this change - confirmed via git stash before/after. Two pre-existing pytest failures unrelated to this work: tests/test_capemeta.py::test_asset_bucket (needs real AWS creds) and tests/test_datalake.py::test_catalog.
*Relevance: high*

*Context: Phase 2 of config-driven S3->SQS notification feature, dispatched as a two-file Fixer task*

*Tags: sqs lambda s3-notifications queue.py phase2*
---
*Observed: 2026-08-05T18:20:44.889Z*