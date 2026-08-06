---
type: source
title: "Observation: Phased commit order + data-centric framing for the notification branch"
slug: obs-2026-08-04-phased-commit-order-data-centric-framing-for-the-notificatio
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: medium
observed_at: 2026-08-04T19:07:49.344Z
tags: ["process", "phasing", "commit-order", "naming", "open-source", "datalake"]
source_context: "Grill-me on the tributary notification plumbing design (seqauto pilot)"
---
# 🔍 Observation: Phased commit order + data-centric framing for the notification branch
Process conventions for the seqauto notification-plumbing branch.

Phased, left-to-right along the user-interaction timeline, one commit per phase: Phase 1 = ETL split-reads output to input-clean + the one crawler-exclude line (standalone, independent of the notifier, deployable/demoable alone); Phase 2 = notifier generalization (glue-etl + notify types) + union per-bucket BucketNotification assembler + notify FIFO queue + pipelines.data.notify[] config (this phase touches the shared notifier, so the replacement guard applies here); Phase 3 = expose the notify queue as a discoverable component attribute for the separate VM branch. Cross-phase coupling to keep in sync: the Phase 2 notify rule prefix must equal the Phase 1 split prefix (both sequencing-reads-split). Phase 2 can be tested independently by writing directly to that prefix, so it is not hard-blocked by Phase 1.

Framing constraint (open-source repo): committable artifacts (config keys, resource names, comments, docs, message field values) must be framed around the DATA and TRANSFORMS - objects landing in the datalake and the notifications they raise - and must NOT name OR imply an unnamed downstream app that consumes them. Prefer data/notification-centric names: notify rule `split-reads` (becomes the message `notification` field), a notification-centric queue name (not `sync`), object-landing comments. The `object-sync` instance-profile service naming lives in the separate VM branch. Plan-internal references to the consumer are for shared understanding only and must not leak into committed code/config/comments.
*Relevance: medium*

*Context: Grill-me on the tributary notification plumbing design (seqauto pilot)*

*Tags: process phasing commit-order naming open-source datalake*
---
*Observed: 2026-08-04T19:07:49.344Z*