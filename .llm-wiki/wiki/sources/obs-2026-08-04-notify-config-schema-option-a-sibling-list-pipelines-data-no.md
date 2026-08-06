---
type: source
title: "Observation: Notify config schema: Option A sibling list pipelines.data.notify[]"
slug: obs-2026-08-04-notify-config-schema-option-a-sibling-list-pipelines-data-no
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T17:12:58.886Z
tags: ["cape-cod", "notifications", "config-schema", "pipelines", "datalake", "plan"]
source_context: "Plan-mode design for seqauto S3->SQS notify plumbing; notify config schema shape"
---
# ⭐ Observation: Notify config schema: Option A sibling list pipelines.data.notify[]
Notify config schema for the seqauto notify plumbing branch is DECIDED as Option A: a sibling list pipelines.data.notify[] parallel to pipelines.data.etl[], parsed with config.get("pipelines","data","notify",default=[]) - the same convention etl[] uses. Each notify entry: name (becomes the message `notification` field), src (bucket id, e.g. input-clean), prefix, suffixes[], and optional queue (default = per-tributary sync queue). Mirrors an etl entry minus script/sink. Chosen over Option B (bucket-level buckets.<id>.notifications[] mirroring the optional crawler block) because it keeps notify in the pipelines family as a consumer type alongside etl, matching the one-mechanism/consumer-types model. Option C (migrate etl[] into a single typed consumers list) is the deferred long-term target, out of scope this branch because it churns hai/genomics/seqauto config + auto-gen public YAML + configure_etl. The datalake wiring reads pipelines.data.notify[], groups by src bucket, and passes per-bucket notify rules + notify-queue name into the unified notifier env. etl[] config stays unchanged. With this, all design decisions for the tributary branch are resolved.
*Relevance: high*

*Context: Plan-mode design for seqauto S3->SQS notify plumbing; notify config schema shape*

*Tags: cape-cod notifications config-schema pipelines datalake plan*
---
*Observed: 2026-08-04T17:12:58.886Z*