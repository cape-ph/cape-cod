---
type: source
title: Deployed Nextflow 26.04.6 passes prefix canary
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: deployed-nextflow-26046-passes-prefix-canary
---

# Deployed Nextflow 26.04.6 passes prefix canary

After deployment, AWS Batch active job-definition revision 53 used ECR digest `sha256:e5b35a7c9f7fb06199fbfb2ed14ab67df420ec3412a4968668549321b54aa9a2`, pushed 2026-09-14. Deployed-image canary `6a34132e-2665-4c9a-9f7e-db0c6909e2f8` ran Nextflow 26.04.6 build 12646 with nf-amazon 3.9.2 on the original `pipeline-output/` root. It completed directory metadata resolution for `micah-test` and its sibling prefixes, found `kraken-debug-0`, passed QC file checks, and exited successfully without child jobs. This validates the production deployment fixed the S3 prefix collision hang. The canary still reports AWS CLI at `/usr/bin/aws` and the generated `cliPath` `/home/ec2-user/miniconda/bin/aws` absent; fix that separate child-submission issue before running the full DAG.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
