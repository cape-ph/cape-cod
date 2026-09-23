---
type: source
title: "Observation: Normal DAP single-read output prefix deleted"
tags:
  - issue-379
  - dap
  - cleanup
  - s3
  - taxprofiler
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-normal-dap-single-read-output-prefix-deleted
relevance: medium
observed_at: 2026-09-23T15:45:06.315Z
source_context: Cleanup after normal DAP validation
---

# 🔍 Observation: Normal DAP single-read output prefix deleted

After verifying the post-deployment normal DAP run, deleted exactly 32 objects under s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/taxprofiler-dap-standard8-rerun-20260923152141/. The prefix now contains zero objects. Durable published Standard-8 assets and representative historical Kraken2 reports were not touched.

*Relevance: medium*
*Context: Cleanup after normal DAP validation*
*Tags: issue-379 dap cleanup s3 taxprofiler*

---
*Observed: 2026-09-23T15:45:06.315Z*
