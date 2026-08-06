---
type: source
title: "Observation: Tributary notification plumbing - delivery-model decision pending EventBridge cost tradeoff"
slug: obs-2026-08-03-tributary-notification-plumbing-delivery-model-decision-pend
status: observation
created: 2026-08-03
updated: 2026-08-03
relevance: high
observed_at: 2026-08-03T20:22:57.269Z
tags: ["datalake", "tributary", "sqs", "notifications", "eventbridge", "planning", "seqauto"]
source_context: "Multi-day planning session for config-driven tributary queue/notification plumbing (seqauto pilot)"
---
# ⭐ Observation: Tributary notification plumbing - delivery-model decision pending EventBridge cost tradeoff
Planning (PLAN.md, plan mode) a reusable, config-driven S3-notification + SQS queue capability on Tributary (capeinfra/datalake/datalake.py), piloted on the seqauto input-clean bucket. Goal: any of a tributary's 4 buckets (input-raw/clean, result-raw/clean) can raise S3 ObjectCreated notifications to a queue by config alone, present-if-configured. Consumer is an external, non-public app (containers watching a filesystem, pull model) that must NOT be named in any committed file; cape-cod delivers only notification + queue + consumer IAM.

Locked: one notification pattern only; DLQ/redrive out of scope; filter at enqueue (not a scheduled cleaner) as primary defense; queue stays FIFO if mediator Lambda wins.

Open, resume here next session: delivery model. Front-runner is a generic config-driven mediator Lambda (S3 -> notifier Lambda that filters + shapes an app-agnostic message -> FIFO queue -> consumer), chosen because use cases need Lambda-level logic beyond S3 native filters (S3 allows only one prefix/one suffix per rule, and only one BucketNotification config per bucket). Live alternative: S3 -> EventBridge -> SQS with event-pattern filtering + input transformer, no Lambda. Deciding axis is COST: runtime/operating cost AND cost-to-change already-deployed infra.

Also open: queue topology (dedicated per notification vs reuse per-tributary src_data_queue), whether to migrate the existing ETL notifier onto the one pattern (recommend: allow later, don't force now), and consumer credential delivery. Verification is pytest + pulumi preview --diff -s cape-cod-dev; never pulumi up; never hand-edit Pulumi.cape-cod-public.yaml.
*Relevance: high*

*Context: Multi-day planning session for config-driven tributary queue/notification plumbing (seqauto pilot)*

*Tags: datalake tributary sqs notifications eventbridge planning seqauto*
---
*Observed: 2026-08-03T20:22:57.269Z*