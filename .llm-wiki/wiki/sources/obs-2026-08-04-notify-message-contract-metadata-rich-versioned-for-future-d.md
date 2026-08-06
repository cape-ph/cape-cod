---
type: source
title: "Observation: Notify message contract: metadata-rich + versioned (for future data-progress tracking)"
slug: obs-2026-08-04-notify-message-contract-metadata-rich-versioned-for-future-d
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T17:06:21.804Z
tags: ["cape-cod", "notifications", "message-contract", "sqs", "plan", "data-progress-tracking"]
source_context: "Plan-mode design for seqauto S3->SQS notify plumbing; notify message contract"
---
# ⭐ Observation: Notify message contract: metadata-rich + versioned (for future data-progress tracking)
Notify message contract for the seqauto notify plumbing branch is DECIDED as metadata-rich and versioned (not just {bucket,key}), motivated by a future goal of tracking data progress through pipelines so a user can see where their data sits. JSON body fields: schema_version (versioned for evolution), event_time, event_name, bucket, key, size, etag, tributary (cape context), notification (the matched notify rule name). These are all derivable from the S3 ObjectCreated event record plus cape config context. Sample/pipeline correlation ids are NOT in the S3 event and would be derived from the object key per-consumer later if needed. FIFO MessageGroupId and content-based dedup are transport-level concerns, separate from the message body. The existing ETL message stays {bucket, key, etl_job} unchanged. With this, no blocking design choices remain for the tributary branch.
*Relevance: high*

*Context: Plan-mode design for seqauto S3->SQS notify plumbing; notify message contract*

*Tags: cape-cod notifications message-contract sqs plan data-progress-tracking*
---
*Observed: 2026-08-04T17:06:21.804Z*