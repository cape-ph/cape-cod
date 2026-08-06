---
type: source
title: "Observation: Notifier replacement risk: preserve logical identity or risk a silent ingest-notification gap"
slug: obs-2026-08-04-notifier-replacement-risk-preserve-logical-identity-or-risk-
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T19:07:39.126Z
tags: ["pulumi", "lambda", "replacement", "datalake", "notifications", "risk"]
source_context: "Grill-me on the tributary notification plumbing design (seqauto pilot)"
---
# ⭐ Observation: Notifier replacement risk: preserve logical identity or risk a silent ingest-notification gap
Grill outcome. Option B runtime-only unification reuses ONE shared notifier Lambda per tributary (Pulumi logical name `{self.name}-lmbdtrgfnct`, role `{self.name}-s3trgrole`, per-src `{self.name}-{src}-allow-lmbd` and `{self.name}-{src}-s3ntfn`; the Lambda has no explicit physical name arg, so it is Pulumi-autonamed from the logical name). Because it is autonamed, changing code, env vars, or the inline role policy are IN-PLACE updates; replacement is triggered only by renaming a logical resource or touching an immutable field.

Risk if a refactor accidentally renames a notifier resource and that reaches deploy: the Lambda is recreated with a new ARN, the per-bucket Permission + BucketNotification must repoint, and during that window s3:ObjectCreated events on the SHARED ingest path can fail to invoke and - with no DLQ (out of scope) - be silently dropped after S3's few async retries. Net effect is a brief, silent ingest-notification gap for hai/genomics/seqauto (uploaded files never trigger their ETL).

Mitigations baked into the plan (not just "remember to check"): (1) preserve resource identity by construction - keep the exact logical names, only ADD the notify env var, the notify-queue put_msg statement, and the new input-clean permission/notification; (2) a unit test asserts notifier logical-name identity + unchanged ETL env when no notify config exists; (3) any replace/delete on the notifier, its role, its permissions, or existing BucketNotifications in `pulumi preview --diff` is a STOP condition before deploy.
*Relevance: high*

*Context: Grill-me on the tributary notification plumbing design (seqauto pilot)*

*Tags: pulumi lambda replacement datalake notifications risk*
---
*Observed: 2026-08-04T19:07:39.126Z*