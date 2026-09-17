---
type: source
title: "Observation: Pulumi preview isolates expected Nextflow update from unrelated churn"
tags:
  - pulumi
  - preview
  - nextflow
  - batch
  - drift
  - deployment
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-pulumi-preview-isolates-expected-nextflow-update-from-unrela
relevance: high
observed_at: 2026-09-14T17:17:12.286Z
source_context: Pulumi preview review after Nextflow 26.04.6 Dockerfile change
---

# ⭐ Observation: Pulumi preview isolates expected Nextflow update from unrelated churn

Pulumi preview succeeded for `cape-cod-dev` after the passphrase was set. Summary: `3 to create, 8 to update, +-1 to replace, 12 changes, 484 unchanged`. The intended Dockerfile-only change is `NXF_VER 25.10.4 -> 26.04.6`. Expected related updates are the nextflow ECR image rebuild, `ccd-pvsl-nextflow-jobdef` revision update, and its IAM policy reference update. The preview also includes recurring Cognito SSO provider metadata drift, demo user temporary-password drift, report-gen manifest/layer asset churn with replacement of immutable Lambda layer `report-gen:24`, and the report Lambda layer reference update. Additional creates are `local-dev@example.com` Cognito user, its Demo Group membership, and a principals DynamoDB item; these originate from ignored local fixture files under `assets-untracked/principals/`, not the Dockerfile diff, and need explicit confirmation before deployment. No bucket, database, queue, or compute environment replacement/deletion appeared. The report-gen replacement is not destructive state, but it is unrelated functional churn and should be accepted or isolated before deploy.

*Relevance: high*
*Context: Pulumi preview review after Nextflow 26.04.6 Dockerfile change*
*Tags: pulumi preview nextflow batch drift deployment*

---
*Observed: 2026-09-14T17:17:12.286Z*
