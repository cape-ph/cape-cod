---
type: source
title: Nextflow 26.04.6 canary validates prefix fix
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: nextflow-26046-canary-validates-prefix-fix
---

# Nextflow 26.04.6 canary validates prefix fix

A final corrected Batch canary used the current Batch image and host but downloaded Nextflow 26.04.6 build 12646 into `/tmp`, unset the image's `NXF_VER=25.10.4`, and loaded nf-amazon 3.9.2. Against the original `pipeline-output/` root, it completed `isDirectory()` for `micah-test`, even though `micah-test-2`, `micah-test-3`, and `micah-test-4` are sibling prefixes. It also completed the `kraken-debug-0` sample directory, QC FASTQ, and QC report existence checks and logged `NEXTFLOW_2604_METADATA_COMPLETED`.

The same metadata canary with Nextflow 25.10.4/nf-amazon 3.4.4 hung at `micah-test`. This validates the upstream Nextflow S3 lookup fix as the remediation for the prefix collision. The permanent Batch image still uses 25.10.4 and has not been changed. The next implementation step is to update `assets/containers/nextflow-kickstart/Dockerfile` to the validated version, run `pulumi preview --diff -s cape-cod-dev`, and let the user perform the deployment. The separate AWS CLI `cliPath` issue remains for a later step.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
