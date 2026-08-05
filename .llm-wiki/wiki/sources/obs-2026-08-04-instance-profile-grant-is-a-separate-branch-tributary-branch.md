---
type: source
title: "Observation: Instance-profile grant is a separate branch; tributary branch only exposes the notify queue"
slug: obs-2026-08-04-instance-profile-grant-is-a-separate-branch-tributary-branch
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T17:03:08.218Z
tags: ["cape-cod", "notifications", "plan", "scope", "instance-profile", "branch-boundary"]
source_context: "Plan-mode scoping of seqauto notify plumbing branch vs instance-profile branch"
---
# ⭐ Observation: Instance-profile grant is a separate branch; tributary branch only exposes the notify queue
Scope split for the seqauto notify plumbing work: the external-consumer EC2 instance-profile grant wiring (adding an object-sync service to _create_instance_profile in capeinfra/swimlanes/private.py) is handled in a SEPARATE branch, not the tributary branch. The tributary branch does NOT touch private.py. Its only obligation toward the consumer is an interface contract: create the notify FIFO queue and expose it as a discoverable component attribute (mirroring capeinfra.data_lakehouse.athena_results_bucket) so the separate branch can grant consume_msg on it; input-clean and result-raw already exist with read/write policies. The tributary branch's pulumi preview should show NO private.py / instance-profile changes. Tributary-branch scope: generalize the notifier Lambda into the unified glue-etl/notify mediator, per-bucket BucketNotification assembly, the notify FIFO queue, seqauto input-clean notify config, and the etl_seqarchive.py new-format output, keeping etl[]/EtlJob/ETLAttrs behavior unchanged.
*Relevance: high*

*Context: Plan-mode scoping of seqauto notify plumbing branch vs instance-profile branch*

*Tags: cape-cod notifications plan scope instance-profile branch-boundary*
---
*Observed: 2026-08-04T17:03:08.218Z*