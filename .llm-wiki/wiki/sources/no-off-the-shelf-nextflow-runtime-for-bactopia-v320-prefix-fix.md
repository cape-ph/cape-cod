---
type: source
title: No off-the-shelf Nextflow runtime for Bactopia v3.2.0 prefix fix
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: no-off-the-shelf-nextflow-runtime-for-bactopia-v320-prefix-fix
---

# No off-the-shelf Nextflow runtime for Bactopia v3.2.0 prefix fix

Research of official releases and source confirms the runtime tradeoff. Nextflow v25.10.4 through v25.10.7 retain the old nf-amazon `S3ObjectSummaryLookup` implementation: bare prefix, unbounded pagination, and no `key + "/"` fallback from PR #6851. Nextflow v26.04.0 and v26.04.6 contain the S3 lookup fix, but Bactopia v3.2.0 fails to parse on 26.04 because its config imports `nextflow.util.SysHelper`. No released version in the checked lines provides both behaviors. The most contained intermediate option is a custom Nextflow 25.10.7 build with PR #6851 backported. Other options require patching/forking Bactopia for Nextflow 26.04 or upgrading Bactopia to a newer major version.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
