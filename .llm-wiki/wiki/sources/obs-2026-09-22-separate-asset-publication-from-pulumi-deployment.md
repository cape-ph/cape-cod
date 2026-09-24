---
type: source
title: "Observation: Separate asset publication from Pulumi deployment"
tags:
  - pipeline-assets
  - publisher
  - pulumi
  - deployment
  - workflow
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-separate-asset-publication-from-pulumi-deployment
relevance: high
observed_at: 2026-09-22T18:11:37.311Z
source_context: Asset publication and deployment flow design
---

# ⭐ Observation: Separate asset publication from Pulumi deployment

The pipeline asset publisher should support manual and automated invocation, but Pulumi should not perform the bulk remote download as a resource side effect. Pulumi can manage the shared meta-assets bucket, lifecycle, IAM, and a small recommended or promoted pointer. A deployment workflow can run a publisher preflight or publisher job before `pulumi preview/up`, then verify the immutable asset manifest exists. The add-asset flow is separate: add a versioned manifest, publish and validate the new immutable S3 prefix, then optionally update a reviewed pointer or pipeline reference and deploy that small reference change. Existing asset versions remain untouched. An asynchronous Pulumi-triggered Batch/Lambda custom resource is possible but not preferred because completion, retries, ownership, and desired-state reconciliation become ambiguous.

*Relevance: high*
*Context: Asset publication and deployment flow design*
*Tags: pipeline-assets publisher pulumi deployment workflow*

---
*Observed: 2026-09-22T18:11:37.311Z*
