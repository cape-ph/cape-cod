---
type: source
title: "Observation: Pipeline asset versions must be immutable and user-selected"
tags:
  - pipeline-assets
  - reproducibility
  - versioning
  - database
  - manifest
  - s3
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-pipeline-asset-versions-must-be-immutable-and-user-selected
relevance: high
observed_at: 2026-09-22T18:08:52.719Z
source_context: Versioning design discussion for shared pipeline assets
---

# ⭐ Observation: Pipeline asset versions must be immutable and user-selected

Pipeline database updates must never replace an existing asset prefix. A new upstream publication creates a new immutable manifest and S3 prefix, for example `kraken2-bracken-standard-8/2026-06-26/` followed by `.../2026-09-30/`; the old version remains available for reproducibility. A catalog may mark a recommended version, but runtime submissions must resolve an explicit asset ID plus version and record the manifest content digest in run metadata. Updating a database means add manifest, publish and validate the new prefix, optionally update a reviewed recommendation pointer, and leave existing runs and references unchanged. S3 object versioning is supplementary protection, not the application-level versioning scheme.

*Relevance: high*
*Context: Versioning design discussion for shared pipeline assets*
*Tags: pipeline-assets reproducibility versioning database manifest s3*

---
*Observed: 2026-09-22T18:08:52.719Z*
