---
type: source
title: Profile contract tests resolve by pipeline ID
status: insight
category: testing
created: 2026-09-25
updated: 2026-09-25
slug: profile-contract-tests-resolve-by-pipeline-id
---

# Profile contract tests resolve by pipeline ID

Updated [[analyses/bactopia-41-cape-cod-implementation-design]]-related profile contract coverage so tests scan the configured analysis-pipeline asset tree and resolve profiles by their logical `pipelineId`, not by a hard-coded filename or subdirectory. The prior v3 file-existence test was replaced with a logical profile-ID availability check. Taxprofiler coverage now verifies the intended `--outdir` requirement while confirming `--input` and `--databases` are not required. Focused infrastructure and taxprofiler tests pass.

*Category: testing*

---
*Captured: 2026-09-25*

## Related

_Add links to related pages._
