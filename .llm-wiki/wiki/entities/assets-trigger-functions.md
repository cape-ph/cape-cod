---
type: entity
title: "assets: trigger functions (assets/trigger-functions/)"
slug: assets-trigger-functions
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["lambda", "s3", "sqs", "glue", "triggers", "assets"]
---

# assets: trigger functions (`assets/trigger-functions/`)

The two Lambdas that connect S3 object arrival to Glue ETL execution via an SQS
FIFO queue. This is the data-lake ingest trigger chain: new object -> S3
notification -> `s3` Lambda -> SQS -> `sqs` Lambda -> Glue job.

## `s3/new_s3obj_queue_notifier_lambda.py`

- Handler `index_handler(event, context)`.
- On S3 bucket notifications, parses each record with
  `capepy.aws.lambda_.BucketNotificationRecord`, walks the key prefix from most
  to least specific, and looks up ETL attributes in DynamoDB via
  `capepy.aws.dynamodb.EtlTable.get_etls(bucket, prefix)`.
- If the object's suffix matches the configured `suffixes`, it enqueues a FIFO
  SQS message `{bucket, key, etl_job}` (message group `<queue>-raw-data-msg`).
- Returns a 200 summary of processed vs ignored objects; 500 on `ClientError`.
- Queue name comes from the `QUEUE_NAME` env var.

## `sqs/sqs_etl_job_trigger_lambda.py`

- Handler `index_handler(event, context)`.
- For each SQS record (parsed with `capepy.aws.lambda_.EtlRecord`), starts the
  named Glue job via
  `glue_client.start_job_run(JobName=etl.job, Arguments={"--SRC_BUCKET_NAME": etl.bucket, "--OBJECT_KEY": etl.key})`.
- Uses partial-batch-failure semantics: any exception requeues that message
  (`batchItemFailures`). A TODO discusses adding a dead-letter queue to avoid a
  "snowball" retry anti-pattern under heavy load.

Wired by `Tributary.configure_src_bucket_notifications` and
`configure_sqs_lambda_target` (see [[entities/datalake-module]],
[[entities/queue-module]]).

Related: [[syntheses/assets-subsystem]], [[entities/pipeline-data-module]].
