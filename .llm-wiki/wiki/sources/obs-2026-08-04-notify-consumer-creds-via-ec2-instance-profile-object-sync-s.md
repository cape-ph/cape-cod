---
type: source
title: "Observation: Notify consumer creds via EC2 instance profile (object-sync service in private swimlane)"
slug: obs-2026-08-04-notify-consumer-creds-via-ec2-instance-profile-object-sync-s
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T17:00:34.087Z
tags: ["cape-cod", "iam", "instance-profile", "private-swimlane", "notifications", "s3-mount", "plan"]
source_context: "Plan-mode design for seqauto S3->SQS notify plumbing; external-consumer credential model"
---
# ⭐ Observation: Notify consumer creds via EC2 instance profile (object-sync service in private swimlane)
For the seqauto notify plumbing branch, external-consumer credentials are delivered via the consumer VM's EC2 instance profile (no IAM user / access keys). The VM is a cape-managed private-swimlane app instance whose profile is built by _create_instance_profile in capeinfra/swimlanes/private.py from a per-instance `services` list. Plan: add a new generic service (e.g. object-sync) to that if-ladder granting consume_msg on the notify FIFO queue, READ on seqauto input-clean, and READ+WRITE on seqauto result-raw, all mount-compatible (s3:ListBucket + GetObject/PutObject for mountpoint-s3 - the VM does S3 read/write over an S3 mount). Reference the queue/buckets via component lookups mirroring the existing athena service that reaches capeinfra.data_lakehouse.athena_results_bucket; do NOT reuse the blanket read-only `s3` service. Open implementation-time details: which instance-app config entry gets the service, and whether the notify-queue + result-raw references resolve at instance-profile construction time given datalake-Tributary vs swimlane ordering. Existing IAM building blocks: get_instance_profile, get_bucket_reader_policy, get_inline_role, SQSQueue consume/put grants.
*Relevance: high*

*Context: Plan-mode design for seqauto S3->SQS notify plumbing; external-consumer credential model*

*Tags: cape-cod iam instance-profile private-swimlane notifications s3-mount plan*
---
*Observed: 2026-08-04T17:00:34.087Z*