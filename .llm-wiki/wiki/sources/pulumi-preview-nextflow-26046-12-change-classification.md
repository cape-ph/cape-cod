---
type: source
title: Pulumi preview Nextflow 26.04.6 change classification
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: pulumi-preview-nextflow-26046-12-change-classification
---

# Pulumi preview Nextflow 26.04.6 change classification

Pulumi preview for stack `cape-cod-dev` succeeded after the stack passphrase became available. Summary: 3 creates, 8 updates, 1 replacement, and 484 unchanged resources. The only tracked source diff outside authored wiki pages is `assets/containers/nextflow-kickstart/Dockerfile`, changing `NXF_VER` from 25.10.4 to the validated 26.04.6.

Expected in-scope cascade: rebuild `nextflow_kickstart` ECR image, update `ccd-pvsl-nextflow-jobdef` to a new immutable revision, and update the IAM policy that references that job-definition ARN. Recurring unrelated changes: Cognito GTRI-SSO providerDetails drift; demo Cognito user temporary-password secret drift; report-gen manifest/layer asset churn; replacement of immutable report-gen Lambda layer revision 24; and the report Lambda layer reference update. Additional creates require review: `local-dev@example.com` Cognito user, its Demo Group membership, and a principals DynamoDB item. These are sourced from ignored local files under `assets-untracked/principals/`, not the Dockerfile diff. No shared buckets, databases, queues, or compute environments were replaced or deleted. The report-gen replacement is non-destructive infrastructure but remains unrelated functional churn that should be accepted or isolated before deployment.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
