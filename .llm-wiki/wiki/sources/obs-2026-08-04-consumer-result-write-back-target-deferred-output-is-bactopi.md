---
type: source
title: "Observation: Consumer result write-back target deferred; output is bactopia-independent"
slug: obs-2026-08-04-consumer-result-write-back-target-deferred-output-is-bactopi
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: medium
observed_at: 2026-08-04T19:07:39.126Z
tags: ["seqauto", "result-raw", "result-clean", "bactopia", "deferred", "instance-profile"]
source_context: "Grill-me on the tributary notification plumbing design (seqauto pilot)"
---
# 🔍 Observation: Consumer result write-back target deferred; output is bactopia-independent
Grill outcome. The external consumer's write-back to a seqauto result bucket is deliberately NOT resolved in the notification-plumbing branch. Its output is a JSON file, is INDEPENDENT of bactopia, and must NOT trigger the existing result-raw bactopia ETLs (bactopia-results: prefix pipeline-output/bactopia-runs, suffixes tsv/yml; bactopia-samples: prefix pipeline-output, suffixes tsv/txt). bactopia runs on the results of the current ETL; the new consumer runs in parallel.

OPEN / deferred to the instance-profile (VM) branch: the write target is undecided - originally result-raw to preserve a later-transform option, but result-clean is now also on the table since the clean-bucket notify mechanism exists; it depends on consumer behavior not yet known (single live file vs write-once). If result-clean, decide whether its crawler (prefix `result`, no excludes today) should skip the JSON. None of this blocks the notification-plumbing branch, which only creates + exposes the notify queue and relies on the consumer's read of input-clean.
*Relevance: medium*

*Context: Grill-me on the tributary notification plumbing design (seqauto pilot)*

*Tags: seqauto result-raw result-clean bactopia deferred instance-profile*
---
*Observed: 2026-08-04T19:07:39.126Z*