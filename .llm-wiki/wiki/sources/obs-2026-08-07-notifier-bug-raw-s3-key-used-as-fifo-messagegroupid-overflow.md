---
type: source
title: "Observation: Notifier bug: raw S3 key used as FIFO MessageGroupId overflows the 128-char SQS limit for long split-read keys"
slug: obs-2026-08-07-notifier-bug-raw-s3-key-used-as-fifo-messagegroupid-overflow
status: observation
created: 2026-08-07
updated: 2026-08-07
relevance: high
observed_at: 2026-08-07T19:00:57.363Z
tags: ["cape-cod", "sqs", "fifo", "messagegroupid", "notifier", "split-reads", "bug", "seqauto", "128-limit", "new_s3obj_queue_notifier_lambda"]
source_context: "Confirmed SQS MessageGroupId 128-char overflow in the seqauto notifier for long split-read keys"
---
# ⭐ Observation: Notifier bug: raw S3 key used as FIFO MessageGroupId overflows the 128-char SQS limit for long split-read keys
Confirmed latent bug in cape-cod notifier: assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py passes the raw S3 object key as the FIFO MessageGroupId. Call site ~line 226: send_notify_message(ddb_table, notify_queue_url, bucket_notif.key, qmsg); send_notify_message forwards it to MessageGroupId (line 76). SQS caps MessageGroupId at 128 chars. Split-read keys of form sequencing-reads-split/<sink_prefix>/<leaf> can exceed 128 (observed: read key 129 chars = 1 over -> InvalidParameterValue; manifest key 110 = under -> enqueues fine, which is why only the manifest landed). Failure is effectively silent: object is already in S3, notifier only logs. Worse, send_notify_message RE-RAISES the ClientError, which propagates to index_handler's outer except ClientError (returns 500), so for that record the downstream ETL enqueue and any remaining batch records are also skipped. S3->Lambda async invoke retries twice then drops, and an oversized key fails deterministically.

Design context (from the FIFO grill note obs-2026-08-04): the group id is intentionally PER-OBJECT-KEY to isolate head-of-line blocking and allow parallel delivery across keys; the notify queue uses CONTENT-BASED dedup (hashes body, event_time sourced from S3 record). So MessageGroupId is independent of dedup - changing the group-id derivation does NOT disturb dedup.

Fix options (pending user direction, no changes made): (1) hash the key: MessageGroupId = sha256(key).hexdigest() (64 chars, bounded, one group per distinct key, preserves per-key parallelism/ordering; downside: not human-readable) - RECOMMENDED; (2) readable prefix + hash suffix, e.g. f"{tributary_name}-{sha256(key).hexdigest()[:32]}" capped to 128 (same safety, debuggable); (3) group by structural component (sink_prefix/sample_id) - changes semantics (serializes leaves under a sink, less parallelism) and still needs a length guard; (4) truncate key to 128 - REJECTED (collides on shared directory prefixes). MessageGroupId allowed chars include alphanumerics + punctuation, so a hex digest is valid.

Secondary hardening decisions (independent of option): (a) decouple notify failures from the ETL path / rest of batch by catching notify errors locally; (b) make failure non-silent via DLQ or CloudWatch alarm on the notify path. Process: fix lives in this repo, deployed shared Lambda (shared-stack deploy-ordering caution applies), wants its own branch/issue separate from #366.
*Relevance: high*

*Context: Confirmed SQS MessageGroupId 128-char overflow in the seqauto notifier for long split-read keys*

*Tags: cape-cod sqs fifo messagegroupid notifier split-reads bug seqauto 128-limit new_s3obj_queue_notifier_lambda*
---
*Observed: 2026-08-07T19:00:57.363Z*