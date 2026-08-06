---
type: source
title: "Observation: Phase 2 notify path validated end-to-end in cape-cod-dev (6 messages, load test)"
slug: obs-2026-08-05-phase-2-notify-path-validated-end-to-end-in-cape-cod-dev-6-m
status: observation
created: 2026-08-05
updated: 2026-08-05
relevance: high
observed_at: 2026-08-05T19:44:39.124Z
tags: ["seqauto", "notify", "sqs", "lambda", "phase2", "validation", "dev"]
source_context: "cape-cod Phase 2 notify-queue live validation in cape-cod-dev"
---
# ⭐ Observation: Phase 2 notify path validated end-to-end in cape-cod-dev (6 messages, load test)
Phase 2 config-driven S3->SQS notify path validated end-to-end in cape-cod-dev after redeploy. Test: deleted all prior sequencing-reads-split artifacts + meta + sequencing-reads originals, re-uploaded both plainreads and gzreads tar.gz files simultaneously (highest available load). Results: ETL ran correctly (unchanged behavior); the unified notifier Lambda (ccd-dlh-T-seqauto-lmbdtrgfnct, physical id ...-f1ac78a) was invoked as expected; exactly 6 messages landed on the notify queue ccd-dlh-T-seqauto-ntfq-q.fifo (3 archived parts per tar.gz x 2 files), confirming per-object-key MessageGroupId parallelism and prefix filtering (only sequencing-reads-split objects notified, no leakage from other input-clean writes/meta). User confirmed message body contract, filtering, notifier CloudWatch (no errors/throttles), and queue attributes (FifoQueue, ContentBasedDeduplication, MessageRetentionPeriod=43200/12h) all look as expected. Pulumi preview earlier showed 4 creates + in-place updates only, no replaces/deletes; logical resource identity of the shared notifier/role/ETL queue preserved. Notify config is present-if-configured: hai/genomics tributaries get code-only lambda update and remain no-op without notify env. Consumer (EC2 instance-profile) and result write-back target remain a separate future branch.
*Relevance: high*

*Context: cape-cod Phase 2 notify-queue live validation in cape-cod-dev*

*Tags: seqauto notify sqs lambda phase2 validation dev*
---
*Observed: 2026-08-05T19:44:39.124Z*