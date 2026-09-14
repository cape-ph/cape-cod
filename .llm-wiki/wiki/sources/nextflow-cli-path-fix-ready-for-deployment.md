---
type: source
title: Nextflow CLI path fix ready for deployment
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: nextflow-cli-path-fix-ready-for-deployment
---

# Nextflow CLI path fix ready for deployment

The deployed-image smoke canary configured `aws.batch.cliPath=/usr/bin/aws` and Nextflow 26.04.6 successfully created child Batch job `12dba23c-0177-4ccf-89f5-faf6106fc9f6`, proving the AWS CLI path was accepted for submission. The child job never started before the parent timeout and was killed by Nextflow, leaving a separate analysis-queue startup/capacity issue to investigate.

The kickstart entrypoint was updated in `assets/containers/nextflow-kickstart/entrypoint.sh` to derive `AWS_CLI_PATH=$(command -v aws)`, fail clearly if the CLI is absent, and write the discovered path into `/nextflow.config`. Shell syntax and diff checks pass. A fresh Pulumi preview shows the expected image, Batch job-definition, and IAM policy updates. The user must deploy this source change before rerunning the smoke canary.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
