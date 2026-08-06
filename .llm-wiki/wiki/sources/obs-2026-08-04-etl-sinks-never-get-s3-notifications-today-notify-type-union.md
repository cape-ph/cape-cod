---
type: source
title: "Observation: ETL sinks never get S3 notifications today; notify type + union-iteration closes the gap"
slug: obs-2026-08-04-etl-sinks-never-get-s3-notifications-today-notify-type-union
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T17:26:03.015Z
tags: ["cape-cod", "datalake", "etl", "notifications", "sink-gap", "bucketnotification", "plan"]
source_context: "Plan-mode design for seqauto notify plumbing; tracing ETL src/sink coupling and notification wiring"
---
# ⭐ Observation: ETL sinks never get S3 notifications today; notify type + union-iteration closes the gap
Real gap found in cape-cod datalake ETL notification wiring: configure_src_bucket_notifications (capeinfra/datalake/datalake.py) attaches an S3 BucketNotification ONLY to buckets in self.sources, and self.sources is populated exclusively from ETL `src` (cfg["src"]) in configure_etl. Nothing ever attaches a notification to a bucket that is only an ETL `sink`. Consequence: you can configure an ETL that writes output to a clean bucket, but nothing can react to that output landing - because sinks never get notifications. This is exactly the seqauto pilot case (seqreadarch writes to its sink input-clean and we want to fire on that). Resolution is NOT to loosen the ETL src/sink coupling (each etl[] entry requires a single src and single sink, both resolved via self.buckets[cfg[...]], a modeling choice not an AWS constraint). Instead: the notify consumer type + one assembler change - attach the unified notifier to the UNION of {ETL source buckets} and {notify source buckets (pipelines.data.notify[] src values)}, emitting exactly ONE aws.s3.BucketNotification per bucket (S3 allows only one per bucket; a bucket that is both an ETL src and notify src must dedupe to one notification targeting the single notifier, which dispatches both types by consulting the ETL DDB table AND the notify env rules for the triggering bucket). A notify entry with src=input-clean wires up the sink bucket; notify has no sink so it never re-triggers the coupling. Genuine ETL loosening (list/optional sink, cross-tributary buckets) stays deferred to the Option C config unification. What src/sink wire up: src = S3 trigger attach + Glue role READ grant + ETLAttrs (bucket,prefix) lookup key; sink = Glue role WRITE grant + --SINK_BUCKET_NAME job arg.
*Relevance: high*

*Context: Plan-mode design for seqauto notify plumbing; tracing ETL src/sink coupling and notification wiring*

*Tags: cape-cod datalake etl notifications sink-gap bucketnotification plan*
---
*Observed: 2026-08-04T17:26:03.015Z*