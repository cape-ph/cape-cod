# Tributary notification plumbing design (seqauto pilot)

Durable design record for the config-driven S3 -> SQS notification work on the
cape-cod datalake, piloted on `seqauto`. Mirrors `PLAN.md` at the decision level
so the design survives independently of the plan file. Companion atomic notes:
[[sources/obs-2026-08-04-delivery-model-locked-extend-mediator-lambda-pattern-eventbr]],
[[sources/obs-2026-08-04-notify-message-contract-metadata-rich-versioned-for-future-d]],
[[sources/obs-2026-08-04-notify-config-schema-option-a-sibling-list-pipelines-data-no]],
[[sources/obs-2026-08-04-instance-profile-grant-is-a-separate-branch-tributary-branch]],
[[sources/obs-2026-08-04-etl-sinks-never-get-s3-notifications-today-notify-type-union]],
[[sources/etl-same-bucket-src-sink-notification-loop]].

## Goal

Add reusable, configuration-driven plumbing so new objects landing in any of a
tributary's four default buckets (`input-raw`, `input-clean`, `result-raw`,
`result-clean`) can raise an S3 notification onto an SQS queue, with
enqueue-time filtering so only objects matching a configured prefix/suffix are
queued. Piloted on `seqauto.input-clean`; usable by any tributary via config
alone (present-if-configured; no config -> no resources, `hai`/`genomics`
unchanged). External consumer exists only in `seqauto` for now.

## Locked decisions

- Delivery model: mediator Lambda (extend the existing ETL notifier), NOT
  EventBridge. Pattern: S3 ObjectCreated -> notifier Lambda (filter, drop
  non-matches, emit cape-owned message) -> FIFO SQS -> consumer. `SQSQueue`
  stays FIFO. EventBridge deferred to a future infra pass.
- ETL path relationship: Option B, RUNTIME-ONLY UNIFICATION. Generalize the one
  notifier Lambda into a rule-driven mediator with two consumer types: `glue-etl`
  (existing `ETLAttrs` DDB lookup, emits `{bucket, key, etl_job}` to the ETL FIFO
  queue) and `notify` (config rules -> notify FIFO queue). UNCHANGED: `etl[]`
  config, `configure_etl`, `EtlJob`, `ETLAttrs`, `src_data_queue`,
  `configure_sqs_lambda_target`, the SQS trigger Lambda, and all ETL dispatch
  behavior. Chosen for pattern coherence (one mechanism, not two parallel
  notifier subsystems), not for fan-out (seqauto needs none).
- Queue topology: queue boundary follows CONSUMER/PURPOSE, not tributary. One
  dedicated notify FIFO queue for the seqauto external consumer, SEPARATE from
  the ETL queue (different principal, different message class). Shared-vs-per-
  tributary generalization deferred until a second consumer opts in.
- Notify config schema: Option A - a sibling list `pipelines.data.notify[]`
  parallel to `pipelines.data.etl[]`, parsed with
  `config.get("pipelines","data","notify",default=[])`. Each entry: `name`
  (-> message `notification` field), `src` (bucket id), `prefix`, `suffixes[]`,
  optional `queue`. Mirrors an etl entry minus `script`/`sink`. Option B
  (bucket-level `buckets.<id>.notifications[]`) and Option C (migrate etl[] into
  one typed consumers list) not chosen; C is the deferred long-term target.
- Notify message contract (cape-owned, metadata-rich, versioned): JSON body
  `schema_version`, `event_time`, `event_name`, `bucket`, `key`, `size`, `etag`,
  `tributary`, `notification`. Motivated by future data-progress tracking.
  Sample/pipeline correlation ids are not in the S3 event; derive from the key
  per-consumer later. FIFO MessageGroupId/dedup are transport-level, separate
  from the body. ETL message stays `{bucket, key, etl_job}`.
- Consumer credentials: the external consumer runs on a cape-provisioned EC2 app
  instance (private swimlane); grants roll into the VM's EC2 instance profile
  (no IAM user/keys), S3 via mountpoint-s3. It needs: consume the notify FIFO
  queue, READ `input-clean`, READ+WRITE seqauto `result-raw`. The instance-
  profile grant wiring (`object-sync` service in `_create_instance_profile`,
  `capeinfra/swimlanes/private.py`) is a SEPARATE branch, NOT this one.

## The real gap this branch closes (sink-side notifications)

Today `configure_src_bucket_notifications` attaches a notification only to
buckets in `self.sources`, populated exclusively from ETL `src`. Nothing
notifies on a bucket that is only an ETL `sink`, so you can configure an ETL
that writes output to a clean bucket with nothing able to react - exactly the
pilot (`seqreadarch` writes to its sink `input-clean`). Fix is NOT to loosen ETL
src/sink; it is the notify consumer type plus one assembler change: attach the
unified notifier to the UNION of {ETL source buckets} and {notify source
buckets}, emitting exactly ONE `aws.s3.BucketNotification` per bucket (S3 allows
one per bucket). A notify entry with `src: input-clean` wires up the sink;
notify has no sink of its own.

Per-bucket coverage the assembler must satisfy:

1. ETL-source-only -> DDB dispatch (works today).
2. notify-source-only (e.g. `input-clean` pilot) -> notify dispatch (new; needs
   the bucket in the union).
3. BOTH (future chained clean-bucket ETL that also notifies) -> one merged
   notification; the single notifier consults DDB AND notify env.
4. ETL-sink with nothing watching -> no notification (add a notify entry with
   `src: B` to react).

## ETL src/sink coupling (probed, kept as-is)

Each `etl[]` entry requires a single `src` and `sink`, both resolved via
`self.buckets[cfg[...]]`. `src` = S3 trigger attach + Glue READ grant + the
`ETLAttrs (bucket, prefix)` lookup key; `sink` = Glue WRITE grant +
`--SINK_BUCKET_NAME` job arg. The pin is a modeling choice, not an AWS
constraint. The code already permits clean-as-src / raw-as-sink and even the
same bucket as both src and sink (no directional validation). This branch keeps
src/sink as-is (the new transform writes to the SAME sink, `input-clean`, new
prefix). Genuine loosening (list/optional sink, cross-tributary buckets) is
deferred to Option C. Same-bucket src=sink is loop-prone with no infra guard -
see the loop known-issue page.

## Interface contract for the separate VM branch

This branch creates the notify FIFO queue and EXPOSES it as a discoverable
component attribute (mirroring `capeinfra.data_lakehouse.athena_results_bucket`)
so the separate instance-profile branch can grant `consume_msg` on it.
`input-clean` and `result-raw` already exist with read/write policies.

## Seqauto end-to-end chain

raw upload -> `input-raw` notification -> `seqreadarch` ETL (gains an additional
transform) writes a new-format output to `input-clean` under a NEW prefix ->
`input-clean` notification (notify rule on that prefix) -> notify FIFO queue ->
external puller on the VM reads, syncs from `input-clean`, writes results to
`result-raw`.

## Out of scope / future

EventBridge multi-consumer eventing; ETL queue consolidation (one shared queue
keyed by MessageGroupId); Option C config unification; DLQ/redrive; the VM
instance-profile wiring. Never run `pulumi up`; verification is `pytest` +
`pulumi preview --diff -s cape-cod-dev`. `Pulumi.cape-cod-public.yaml` is
auto-generated - do not hand-edit.
