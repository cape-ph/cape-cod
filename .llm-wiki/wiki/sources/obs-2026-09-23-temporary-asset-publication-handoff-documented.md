---
type: source
title: "Observation: Temporary asset publication handoff documented"
tags:
  - pipeline-assets
  - cape-cod-env
  - ansible
  - pulumi
  - issue-387
  - documentation
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-temporary-asset-publication-handoff-documented
relevance: high
observed_at: 2026-09-23T16:17:49.371Z
source_context: Closing the temporary deployment knowledge gap
---

# ⭐ Observation: Temporary asset publication handoff documented

Added a concise transitional ownership subsection to extra-doc/README.pipeline-assets.md. It states that Pulumi does not publish large assets, the current Standard-8 asset is already published and needs no post-Pulumi publication, new versions remain out-of-band, and the note is removed when Ansible owns the handoff. Created GitHub issue #387 to move publication to cape-cod-env without changing the manifest, S3 layout, or runtime export contract.

*Relevance: high*
*Context: Closing the temporary deployment knowledge gap*
*Tags: pipeline-assets cape-cod-env ansible pulumi issue-387 documentation*

---
*Observed: 2026-09-23T16:17:49.371Z*
