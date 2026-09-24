---
type: source
title: "Observation: Dynamic systemd volume mounter is a viable host-EFS architecture"
tags:
  - pipeline
  - architecture
  - systemd
  - efs
  - volume
  - registry
  - nextflow
  - aws
  - batch
  - generic
  - resources
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-dynamic-systemd-volume-mounter-is-a-viable-host-efs-architec
relevance: critical
observed_at: 2026-09-18T15:31:24.838Z
source_context: "Issue #379 generic resource dependency discussion"
---

# 🔴 Observation: Dynamic systemd volume mounter is a viable host-EFS architecture

Refined desired state for generic CAPE pipeline resources: a static host-mounted EFS AMI is too limited, but option 1 can be dynamic. A host-side systemd mounter/agent can consume an external logical-volume registry, resolve current physical EFS IDs, mount any declared set of resources at stable host paths, and refresh mounts when IDs change. Nextflow can continue using aws.batch.volumes host-path mappings, so no Nextflow or nf-amazon fork is required. This creates a host-fleet coordination problem rather than a one-time AMI configuration problem: new hosts need the mounter, desired mounts must be synchronized before tasks run, mount changes need validation/drain behavior, and the runtime must generate the child host-path list from logical pipeline dependencies. A static mount is a tactical subset; direct ECS-managed child EFS remains a heavier alternative.

*Relevance: critical*
*Context: Issue #379 generic resource dependency discussion*
*Tags: pipeline architecture systemd efs volume registry nextflow aws batch generic resources*

---
*Observed: 2026-09-18T15:31:24.838Z*
