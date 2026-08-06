---
type: source
title: "Observation: Tributary notify plumbing: chose Option B (runtime-only notifier unification)"
slug: obs-2026-08-04-tributary-notify-plumbing-chose-option-b-runtime-only-notifi
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T16:45:00.752Z
tags: ["cape-cod", "datalake", "notifications", "sqs", "etl", "pulumi", "plan"]
source_context: "Plan-mode design for config-driven tributary S3->SQS notification plumbing (seqauto pilot)"
---
# ⭐ Observation: Tributary notify plumbing: chose Option B (runtime-only notifier unification)
For the seqauto S3->SQS notification plumbing branch, the delivery approach was decided as Option B "runtime-only unification": generalize the single notifier Lambda (assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py) into a rule-driven mediator with two consumer types (glue-etl = existing ETLAttrs/DDB lookup emitting {bucket,key,etl_job} to the ETL FIFO queue; notify = config-driven prefix/suffix rules emitting a cape-owned message to a new notify FIFO queue), and generalize configure_src_bucket_notifications in capeinfra/datalake/datalake.py to assemble all of a bucket's targets into one aws.s3.BucketNotification. Kept unchanged: etl[] config, configure_etl, EtlJob, ETLAttrs, ETL queue/trigger behavior (proven via pulumi preview showing in-place notifier Lambda/role updates, not replace). Chosen over A-prime (separate notifier now, ETL cutover later) for PATTERN COHERENCE - avoiding two parallel notifier subsystems a future tributary author must choose between - not for fan-out. seqauto has no same-bucket fan-out: the seqreadarch ETL triggers on input-raw and the notify rule watches input-clean. The branch also updates etl_seqarchive.py to add an additional transform writing a new-format output to input-clean under a new prefix/suffix, which is what the external consumer's notify rule watches. Rationale accepted because the full end-to-end path must be exercised for the demo regardless, so B adds only hai regression + preview scrutiny, not new demo testing. Plan captured in PLAN.md.
*Relevance: high*

*Context: Plan-mode design for config-driven tributary S3->SQS notification plumbing (seqauto pilot)*

*Tags: cape-cod datalake notifications sqs etl pulumi plan*
---
*Observed: 2026-08-04T16:45:00.752Z*