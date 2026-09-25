---
type: source
title: "Observation: Taxprofiler profile move leaves one stale test path"
tags:
  - taxprofiler
  - dap
  - profile
  - tests
  - paths
  - review
status: observation
created: 2026-09-25
updated: 2026-09-25
slug: obs-2026-09-25-taxprofiler-profile-move-leaves-one-stale-test-path
relevance: high
observed_at: 2026-09-25T16:40:50.501Z
source_context: Review of latest cape-cod analysis pipeline profile move
---

# ⭐ Observation: Taxprofiler profile move leaves one stale test path

Reviewed commit 8665ef7. Moving taxprofiler-kraken2-2.0.1.json from assets/analysis-pipelines/bactopia/ to assets/analysis-pipelines/taxprofiler/ is compatible with DAPRegistry's recursive JSON glob and preserves the pipeline ID/resource stem. One required update remains: tests/test_bactopia_v4_contract.py::_load_profile hard-codes the bactopia directory, so test_taxprofiler_kraken2_profile_has_runtime_policy fails with FileNotFoundError. Current design wiki references at analyses/bactopia-41-cape-cod-implementation-design.md lines 315 and 889 also use the old path; historical observation pages should remain unchanged. The commit's required schema change to only --outdir is reflected in the profile but lacks a regression assertion; submit_dap_run.py does not validate the JSON schema itself, so the optional input/databases behavior should remain intentional and documented.

*Relevance: high*
*Context: Review of latest cape-cod analysis pipeline profile move*
*Tags: taxprofiler dap profile tests paths review*

---
*Observed: 2026-09-25T16:40:50.501Z*
