---
type: source
title: "Observation: Direct S3 dump to unprocessed/ did not fire the ETL - suspected deploy/runtime, config is correct"
slug: obs-2026-08-04-direct-s3-dump-to-unprocessed-did-not-fire-the-etl-suspected
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T20:49:24.976Z
tags: ["seqauto", "etl", "s3-notification", "troubleshooting", "deploy", "dynamodb", "glue"]
source_context: "Phase 1 testing: direct S3 dump to unprocessed/ did not trigger the ETL"
---
# ⭐ Observation: Direct S3 dump to unprocessed/ did not fire the ETL - suspected deploy/runtime, config is correct
User dumped the two test `.tar.gz` archives directly into the seqauto input-raw bucket's `unprocessed/` prefix (bypassing the front end) WITHOUT deploying the branch, expecting the already-deployed old ETL to fire. Nothing happened.

Repo analysis says the config is correct for these files: the input-raw `BucketNotification` uses `events=["s3:ObjectCreated:*"]` with no S3-level prefix/suffix filter, the notifier computes suffix as the final dot-segment (`.tar.gz` -> `"gz"`), and `seqreadarch` has `prefix: unprocessed`, `suffixes: [gz, tar]`, so `"gz"` matches. This branch touches neither the trigger path nor the ETL config (only the crawler `excludes` line + ETL output), and the `gz` suffix has been committed since 2025-08. So the split-reads changes are NOT what's blocking a trigger. Conclusion: this is a deployed-state/runtime problem, not config logic.

Diagnostic order for next session (agent can't hit AWS here - invalid token): (1) `aws s3api get-bucket-notification-configuration --bucket <seqauto-input-raw>` - expect a Lambda config `s3:ObjectCreated:*` -> notifier `*-lmbdtrgfnct`; empty = drift / not deployed, which alone explains it. (2) notifier CloudWatch logs around upload time - invoked? "ignored due to not passing filter criteria"? exception? (3) ETLAttrs DDB row for (input-raw bucket name, `unprocessed`) with suffixes including `gz` - a stale deploy could omit `gz` even though the YAML has it. (4) confirm objects are directly under `unprocessed/` in the real src bucket. (5) downstream ETL FIFO queue + SQS-trigger Lambda + Glue run history. Note: the pile of old `.tar` files in `unprocessed/` does NOT prove the S3-notification path is currently live. User plans to deploy and retest tomorrow AM.
*Relevance: high*

*Context: Phase 1 testing: direct S3 dump to unprocessed/ did not trigger the ETL*

*Tags: seqauto etl s3-notification troubleshooting deploy dynamodb glue*
---
*Observed: 2026-08-04T20:49:24.976Z*