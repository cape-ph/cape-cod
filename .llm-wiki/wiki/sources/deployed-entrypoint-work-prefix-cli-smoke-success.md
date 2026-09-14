---
type: source
title: Deployed entrypoint work-prefix CLI smoke success
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: deployed-entrypoint-work-prefix-cli-smoke-success
---

# Deployed entrypoint work-prefix CLI smoke success

The final actual-entrypoint canary `a11efe98-66f2-4f40-af00-881435123a6b` succeeded on Batch job definition 55 and the deployed Nextflow 26.04.6 image. The entrypoint dynamically resolved AWS CLI as `/usr/bin/aws`, generated a work directory under `s3://nextflow-spot-batch-temp-<jobid>/work`, and ran a trivial Nextflow process through AWS Batch. Child job `3e4df4c1-cbd8-48ae-b554-8c9168fc6b05` started and succeeded. The temporary work bucket was cleaned up normally. This validates the dynamic CLI path and the narrow S3 work-prefix fix in the real deployed entrypoint. The KRAKEN2 selector warning was expected for the smoke pipeline and harmless.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
