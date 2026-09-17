---
type: source
title: "Observation: No released Nextflow version currently satisfies both constraints"
tags:
  - nextflow
  - bactopia
  - runtime
  - compatibility
  - s3
  - prefix
  - collision
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-no-released-nextflow-version-currently-satisfies-both-constr
relevance: high
observed_at: 2026-09-14T18:47:44.346Z
source_context: Intermediate Nextflow release research
---

# ⭐ Observation: No released Nextflow version currently satisfies both constraints

Release/source research found no obvious off-the-shelf Nextflow version that both preserves Bactopia v3.2.0 compatibility and contains the S3 prefix-collision fix. Nextflow v25.10.4, v25.10.5, v25.10.6, and v25.10.7 all retain the old `S3ObjectSummaryLookup` unbounded bare-prefix implementation without the `key + "/"` fallback from PR #6851. Nextflow v26.04.0 and v26.04.6 contain the #6851 two-call lookup fix, but Bactopia v3.2.0 fails to parse on them because its config imports `nextflow.util.SysHelper`. The most contained option 4 is a custom Nextflow 25.10.7 build with PR #6851 backported; alternatives are a Bactopia compatibility fork for Nextflow 26.04 or a larger Bactopia upgrade.

*Relevance: high*
*Context: Intermediate Nextflow release research*
*Tags: nextflow bactopia runtime compatibility s3 prefix collision*

---
*Observed: 2026-09-14T18:47:44.346Z*
