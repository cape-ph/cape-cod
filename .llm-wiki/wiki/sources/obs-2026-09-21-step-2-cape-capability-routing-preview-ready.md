---
type: source
title: "Observation: Step 2 CAPE capability routing preview ready"
tags:
  - issue-379
  - step2
  - pulumi
  - preview
  - batch
  - capability
  - taxprofiler
  - efs
status: observation
created: 2026-09-21
updated: 2026-09-21
slug: obs-2026-09-21-step-2-cape-capability-routing-preview-ready
relevance: high
observed_at: 2026-09-21T13:54:31.102Z
source_context: CAPE Cod Step 2 implementation and preview
---

# ⭐ Observation: Step 2 CAPE capability routing preview ready

Implemented the bounded Issue #379 Step 2 slice in the CAPE Cod working tree and stopped before runtime validation. Added a dev-only taxonomic-reference-data Batch capability environment using the retained EFS-capable AMI, launch-template bootstrap user data for the AMI mounter contract, reuse of the EFS-authorized analysis security group, and logical taxonomic-profiling to queue routing. The submit handler preserves the legacy queue fallback and rejects unknown execution classes. Python compilation, 22 focused tests, Ruff, JSON parsing, LSP diagnostics, and git diff --check pass. The final Pulumi preview succeeds with 20 creates, 8 updates, and 488 unchanged resources; the 17 additional creates over the Step 1 baseline are the capability pool and expected child resources. Existing SSO, S3, Docker, parent Nextflow job-definition, DAP, and IAM churn remains in the baseline/known preview set. No deploy, EFS sentinel, or real taxprofiler run was performed. Owner review is now required.

*Relevance: high*
*Context: CAPE Cod Step 2 implementation and preview*
*Tags: issue-379 step2 pulumi preview batch capability taxprofiler efs*

---
*Observed: 2026-09-21T13:54:31.102Z*
