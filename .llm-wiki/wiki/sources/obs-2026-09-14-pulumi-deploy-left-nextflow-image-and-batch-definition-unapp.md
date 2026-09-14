---
type: source
title: "Observation: Pulumi deploy left Nextflow image and Batch definition unapplied"
tags:
  - pulumi
  - deploy
  - nextflow
  - batch
  - image
  - validation
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-pulumi-deploy-left-nextflow-image-and-batch-definition-unapp
relevance: high
observed_at: 2026-09-14T17:27:06.850Z
source_context: Post-deploy AWS resource verification
---

# ⭐ Observation: Pulumi deploy left Nextflow image and Batch definition unapplied

Post-deploy validation for account 767397883306 and stack cape-cod-dev found the active `ccd-pvsl-nextflow-jobdef` remains revision 52 using the old image digest `sha256:1ea92725c2f192f89a0a81f3d7cf17dc94041291fa9fa14d76dd51f68e531947`, pushed 2026-06-08. The ECR tag `ccd-pvsl-repo-nextflow_kickstart` still points to that digest. A fresh Pulumi preview still shows the Nextflow ECR image update, Batch job-definition update, and IAM policy update pending, along with accepted local-dev fixture creates and report-gen layer replacement. Therefore the deployment did not apply the Nextflow image/job-definition change; a canary run now would still use Nextflow 25.10.4 and would not validate the fix.

*Relevance: high*
*Context: Post-deploy AWS resource verification*
*Tags: pulumi deploy nextflow batch image validation*

---
*Observed: 2026-09-14T17:27:06.850Z*
