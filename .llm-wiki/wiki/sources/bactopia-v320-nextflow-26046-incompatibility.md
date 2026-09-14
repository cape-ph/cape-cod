---
type: source
title: Bactopia v3.2.0 Nextflow 26.04.6 incompatibility
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: bactopia-v320-nextflow-26046-incompatibility
---

# Bactopia v3.2.0 Nextflow 26.04.6 incompatibility

The new full-run parent Batch job `d222690a-e6e2-4535-861f-cb4957d4e0d9` failed immediately with deployed Nextflow 26.04.6 before running workflow processes. The CloudWatch stream `ccd-pvsl-nextflow-jobdef/default/04f91d7d06404874af691e96421a7ad0` reports `Error nextflow.config:12:8: Unexpected input: 'nextflow'` at `import nextflow.util.SysHelper`. Bactopia v3.2.0's upstream `nextflow.config` imports `nextflow.util.SysHelper` and uses `SysHelper.getAvailMemory()` and `SysHelper.getAvailCpus()` later in the file. The runtime API is unavailable or incompatible in Nextflow 26.04.6. This is independent of the fixed S3 prefix collision, Docker DNS, work-prefix, and AWS CLI path issues. Full E2E runs are blocked until Bactopia v3.2.0 is patched or upgraded, or the runtime/data-layout strategy changes.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
