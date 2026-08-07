---
type: source
title: "Observation: Fix #368: bounded notifier FIFO MessageGroupId (readable prefix + sha256) and decoupled notify failures"
slug: obs-2026-08-07-fix-368-bounded-notifier-fifo-messagegroupid-readable-prefix
status: observation
created: 2026-08-07
updated: 2026-08-07
relevance: high
observed_at: 2026-08-07T19:29:00.168Z
tags: ["cape-cod", "sqs", "fifo", "messagegroupid", "notifier", "split-reads", "fix", "issue-368", "seqauto", "hashlib", "decouple", "new_s3obj_queue_notifier_lambda"]
source_context: "Implementing the #368 notifier MessageGroupId 128-char fix on branch 368"
---
# ⭐ Observation: Fix #368: bounded notifier FIFO MessageGroupId (readable prefix + sha256) and decoupled notify failures
Fix implemented for issue #368 on branch 368-fix-notifier-messagegroupid-128-limit (based off gh/363 tip 5c0c352, the currently-deployed branch, so a deploy stays a superset of live). File: assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py. Root cause was the notifier passing the raw S3 key as the FIFO MessageGroupId, overflowing the SQS 128-char limit for long split-read keys (see [[sources/obs-2026-08-07-notifier-bug-raw-s3-key-used-as-fifo-messagegroupid-overflow]]).

Changes: (1) added `import hashlib`; (2) new pure helper derive_message_group_id(key, prefix) -> f"{prefix[:63]}-{sha256(key.encode('utf-8')).hexdigest()}" which is always <=128 chars (63 readable prefix + '-' + 64 hex) and preserves per-object-key semantics (distinct keys -> distinct groups, parallel delivery across keys, per-key ordering) since the digest is over the full key; (3) at the notify call site, group_id is computed with prefix = tributary_name or notification or "notify" and passed to send_notify_message instead of bucket_notif.key; (4) the send_notify_message call is wrapped in a local try/except ClientError that logs via ddb_table.logger.exception and continues, so a notify failure no longer aborts the ETL path or the rest of the batch (decouple); (5) send_notify_message docstring updated to describe the bounded derivation instead of "per-object-key". send_notify_message itself still raises (kept generic). Content-based dedup on the queue hashes the body, so the group-id change does not affect dedup.

Scope decisions: chose Option 2 (readable prefix + hash) and the decouple hardening; DLQ/CloudWatch alarm on the notify path deferred (no Pulumi/infra change this issue). Verified locally: ruff check clean on the file, LSP clean, and a determinism/length test asserted len<=128 for 110/129/4000-char keys across short and long prefixes, deterministic output, and distinct keys yield distinct ids (module itself not importable locally because capepy is not installed, so the test replicated the helper's exact expression and cross-checked it against the source via grep). Not yet committed at time of this note; commit/push gated on explicit user approval, and deploy is user-run on the shared cape-cod-dev stack.
*Relevance: high*

*Context: Implementing the #368 notifier MessageGroupId 128-char fix on branch 368*

*Tags: cape-cod sqs fifo messagegroupid notifier split-reads fix issue-368 seqauto hashlib decouple new_s3obj_queue_notifier_lambda*
---
*Observed: 2026-08-07T19:29:00.168Z*