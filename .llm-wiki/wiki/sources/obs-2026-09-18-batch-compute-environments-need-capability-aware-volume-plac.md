---
type: source
title: "Observation: Batch compute environments need capability-aware volume placement"
tags:
  - aws
  - batch
  - compute
  - environment
  - capabilities
  - volumes
  - efs
  - placement
  - architecture
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-batch-compute-environments-need-capability-aware-volume-plac
relevance: critical
observed_at: 2026-09-18T16:08:08.736Z
source_context: "Issue #379 generic resource dependency discussion"
---

# 🔴 Observation: Batch compute environments need capability-aware volume placement

Current CAPE BatchCompute models instance types, AMI, subnets, security group, and vCPU capacity, but not host-mounted volume capabilities. With one analysis queue pointing to one compute environment, any dynamic child can land on any eligible host. A dynamic systemd mounter can refresh EFS IDs without rebuilding hosts, but it does not solve placement unless every eligible host mounts the union of possible resources or the scheduler routes jobs to a capability-specific queue. The generic design should distinguish job resource requirements from compute-environment capabilities and volume dependencies, then resolve logical volume refs to a compatible queue/host class. Mounting every possible resource on every host is not a good final assumption for arbitrary N volumes or sensitive shared datasets.

*Relevance: critical*
*Context: Issue #379 generic resource dependency discussion*
*Tags: aws batch compute environment capabilities volumes efs placement architecture*

---
*Observed: 2026-09-18T16:08:08.736Z*
