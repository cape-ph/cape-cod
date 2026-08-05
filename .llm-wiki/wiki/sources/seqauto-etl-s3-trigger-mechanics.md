---
type: source
title: "seqauto ETL S3 trigger chain + notifier prefix/suffix matching"
slug: seqauto-etl-s3-trigger-mechanics
status: insight
created: 2026-08-04
updated: 2026-08-04
category: architecture
---
# seqauto ETL S3 trigger chain + notifier prefix/suffix matching
How a new object in a seqauto ETL source bucket gets processed (all pre-existing infra; independent of the split-reads change).

**Chain:** S3 `ObjectCreated` -> notifier Lambda -> ETL FIFO SQS queue -> SQS-trigger Lambda -> Glue job.

**Wiring** (`capeinfra/datalake/datalake.py`, `configure_src_bucket_notifications` ~line 527): one notifier Lambda per datalake (`{name}-lmbdtrgfnct`, code = `assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py`, env `QUEUE_NAME`/`ETL_ATTRS_DDB_TABLE`/`DDB_REGION`). For each ETL source bucket it creates a `lambda.Permission` + an `aws.s3.BucketNotification` with `events=["s3:ObjectCreated:*"]` and NO `filter_prefix`/`filter_suffix` - every object create in the bucket invokes the notifier; all filtering is in the Lambda.

**Notifier matching** (`new_s3obj_queue_notifier_lambda.py`, `index_handler`): for each record, `key.rpartition("/")` -> `(prefix, objname)`; `suffix = objname.rpartition(".")[2]` (so `foo.tar.gz` -> `"gz"`, `foo.tar` -> `"tar"`). Then it walks prefixes upward (`prefix = prefix.rpartition("/")[0]`), calling `EtlTable.get_etls(bucket, prefix)`; on a hit, if `suffix in etl_attrs["suffixes"]` it enqueues `{bucket, key, etl_job}` to the ETL FIFO queue with static `MessageGroupId = f"{queue_name}-raw-data-msg"`. No match on any ancestor prefix -> ignored.

**Implications:** the DEPLOYED ETLAttrs DynamoDB table is the runtime source of truth for `(bucket, prefix) -> suffixes/etl_job`, populated by `configure_etl` at deploy time. Changing `prefix`/`suffixes` in `Pulumi.*.yaml` has NO runtime effect until a deploy updates the DDB. Because suffix = final dot-segment, `[gz, tar]` matches both `.tar` and `.tar.gz`. This is the same mediator Lambda the notify work extends - see [[sources/obs-2026-08-04-etl-sinks-never-get-s3-notifications-today-notify-type-union]].
*Category: architecture*
---
*Captured: 2026-08-04*
## Related
_Add links to related pages._