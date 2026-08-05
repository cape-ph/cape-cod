---
type: source
title: "Observation: Delivery model locked: extend mediator-Lambda pattern, EventBridge deferred to future infra pass"
slug: obs-2026-08-04-delivery-model-locked-extend-mediator-lambda-pattern-eventbr
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T15:10:31.261Z
tags: ["datalake", "tributary", "sqs", "notifications", "eventbridge", "planning", "seqauto", "delivery-model"]
source_context: "Multi-day planning: config-driven tributary S3-notification + queue plumbing (seqauto pilot)"
---
# ⭐ Observation: Delivery model locked: extend mediator-Lambda pattern, EventBridge deferred to future infra pass
Delivery-model decision LOCKED for the tributary notification plumbing branch (PLAN.md): extend the existing mediator-Lambda pattern to all four tributary buckets, config-driven. EventBridge was evaluated and deferred to a future infra pass. Rationale: for this branch's need (triggered functions on clean buckets), EventBridge's only genuine ease-of-implementation win is multiple independent consumers on ONE bucket via S3 event fan-out, and this branch does not need that - the seqauto pilot targets input-clean, which has no existing notifications (it is an ETL sink, not a source), so there is exactly one target and no fan-out. Keeping the mediator Lambda preserves the app-owned message contract and in-code filtering. Queue stays FIFO.

ETL path stays untouched this branch (no forced EventBridge migration). Reusable-design constraint that remains: notifications must be assembled PER BUCKET into a single aws.s3.BucketNotification (a second resource clobbers the first), so a bucket that is both an ETL source and a notification target needs aggregated targets; seqauto pilot does not hit this. Also noted: current ETL notifier uses a single static FIFO MessageGroupId so each tributary queue processes serially today.

Parked for a future infra-simplification pass (no production system yet, only integration env): EventBridge as multi-consumer eventing layer, ETL queue consolidation (one shared queue with MessageGroupId per tributary/source bucket), general cost review.

Still open for this branch: sync-queue topology (decided by whether one external consumer serves all tributaries or one per tributary) and consumer credential delivery.
*Relevance: high*

*Context: Multi-day planning: config-driven tributary S3-notification + queue plumbing (seqauto pilot)*

*Tags: datalake tributary sqs notifications eventbridge planning seqauto delivery-model*
---
*Observed: 2026-08-04T15:10:31.261Z*