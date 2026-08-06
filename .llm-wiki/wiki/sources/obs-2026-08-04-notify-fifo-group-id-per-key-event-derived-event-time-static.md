---
type: source
title: "Observation: Notify FIFO group id per-key + event-derived event_time; static ETL group id is a latent serial limit"
slug: obs-2026-08-04-notify-fifo-group-id-per-key-event-derived-event-time-static
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T19:07:20.935Z
tags: ["sqs", "fifo", "messagegroupid", "dedup", "datalake", "notifications"]
source_context: "Grill-me on the tributary notification plumbing design (seqauto pilot)"
---
# ⭐ Observation: Notify FIFO group id per-key + event-derived event_time; static ETL group id is a latent serial limit
Grill outcome. The new seqauto notify FIFO queue will use a PER-OBJECT-KEY MessageGroupId (not the static id the ETL queues use), and the notify message body's `event_time` must be sourced from the S3 record's `eventTime`/sequencer, never Lambda wall-clock, so content-based dedup collapses S3 at-least-once redeliveries within the 5-minute FIFO window.

Key facts established: MessageGroupId is queue-local and never couples two queues, so mixing group-id strategies across queues has no system-level downside - it only sets, within one queue, ordering scope (strict per group) and the parallelism/head-of-line ceiling (one in-flight message per active group). Per-key isolates head-of-line blocking to a single key and enables parallel delivery across keys, and is strictly more flexible even for a single-threaded puller (enables concurrency without requiring it). FIFO throughput cap is 300 msg/s (3000 batched) regardless of group count, far above seqauto volume.

LATENT LIMITATION noted (NOT fixed this branch): the existing ETL notifier uses a single static group id `f"{queue_name}-raw-data-msg"`, which serializes each ETL queue - a stuck message head-of-line blocks the rest until visibility timeout/DLQ. Retrofitting it touches deployed ETL behavior and belongs in the deferred ETL-consolidation pass. Add a one-line rationale comment on each queue so the two conventions read intentionally.
*Relevance: high*

*Context: Grill-me on the tributary notification plumbing design (seqauto pilot)*

*Tags: sqs fifo messagegroupid dedup datalake notifications*
---
*Observed: 2026-08-04T19:07:20.935Z*