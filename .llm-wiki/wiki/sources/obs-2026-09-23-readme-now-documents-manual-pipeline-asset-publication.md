---
type: source
title: "Observation: README now documents manual pipeline asset publication"
tags:
  - pipeline-assets
  - readme
  - cape-cod-env
  - issue-387
  - documentation
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-readme-now-documents-manual-pipeline-asset-publication
relevance: high
observed_at: 2026-09-23T20:33:49.837Z
source_context: Issue 379 documentation closeout
---

# ⭐ Observation: README now documents manual pipeline asset publication

Updated `README.md` to state that Pulumi does not publish large pipeline assets and that new versions require a manual publication step documented in `extra-doc/README.pipeline-assets.md`. Updated the sub-readme with the transitional manual deployment wording. Commented on cape-cod issue #387 that the migration must update both README files when publication moves to the environment-owned flow. README validation passed with no `cape-cod-env` reference in the main README and `git diff --check` clean.

*Relevance: high*
*Context: Issue 379 documentation closeout*
*Tags: pipeline-assets readme cape-cod-env issue-387 documentation*

---
*Observed: 2026-09-23T20:33:49.837Z*
