---
type: source
title: "Observation: Phase 3: notify queue exposed via config-keyed DatalakeHouse.notify_queues (no hard-coded names)"
slug: obs-2026-08-05-phase-3-notify-queue-exposed-via-config-keyed-datalakehouse-
status: observation
created: 2026-08-05
updated: 2026-08-05
relevance: high
observed_at: 2026-08-05T20:02:28.221Z
tags: ["seqauto", "notify", "datalake", "discoverability", "phase3", "instance-profile"]
source_context: "cape-cod seqauto notify branch Phase 3 - notify queue discoverability"
---
# ⭐ Observation: Phase 3: notify queue exposed via config-keyed DatalakeHouse.notify_queues (no hard-coded names)
Phase 3 (final commit of the seqauto notify branch) exposes the notify queue for the separate consumer-grant branch via DatalakeHouse.notify_queues: a config-keyed dict (key = tributary config name, e.g. \"seqauto\"; value = the tributary's SQSQueue) populated in configure_tributaries only for tributaries whose config declares a notify block (present-if-configured). No tributary name is hard-coded anywhere - keys derive from trib_config.get(\"name\") in the same loop that wills tributaries into being. The separate instance-profile branch resolves capeinfra.data_lakehouse.notify_queues[\"seqauto\"] (mirroring how private.py reaches capeinfra.data_lakehouse.athena_results_bucket - same stack, in-process attribute, no StackReference/export). SQSQueue already exposes PolicyEnum.consume_msg (ReceiveMessage/DeleteMessage/GetQueueAttributes), so the consumer branch attaches that; this branch only exposes the queue object. Resolving a name with no notify queue raises KeyError at synth time (loud fail beats silently granting nothing). notify_queues is pure Python and provisions no AWS resources: pulumi preview -s cape-cod-dev showed 1 update / 474 unchanged, the lone update being pre-existing GTRI-SSO cognito cert-rotation drift, no destructive ops. Still deferred to the separate branch: the private.py instance-profile consume_msg grant and the undecided result write-back target (result-raw vs result-clean).
*Relevance: high*

*Context: cape-cod seqauto notify branch Phase 3 - notify queue discoverability*

*Tags: seqauto notify datalake discoverability phase3 instance-profile*
---
*Observed: 2026-08-05T20:02:28.221Z*