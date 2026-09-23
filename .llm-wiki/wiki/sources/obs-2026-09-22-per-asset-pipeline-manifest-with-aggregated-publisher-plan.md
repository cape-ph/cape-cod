---
type: source
title: "Observation: Per-asset pipeline manifest with aggregated publisher plan"
tags:
  - pipeline-assets
  - manifest
  - publisher
  - s3
  - meta-assets
  - pulumi
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-per-asset-pipeline-manifest-with-aggregated-publisher-plan
relevance: high
observed_at: 2026-09-22T18:01:33.238Z
source_context: Design discussion for remote pipeline asset publication
---

# ⭐ Observation: Per-asset pipeline manifest with aggregated publisher plan

For remote pipeline assets, prefer one small declarative manifest per asset or immutable asset version under a repository directory, rather than one hand-maintained monolithic manifest or embedding large payloads in Pulumi. A publisher scans and validates all manifests into one aggregate plan, but can publish one changed asset by ID. Shared assets such as Kraken2 Standard-8 belong under a shared manifest with consumer references; pipeline-specific assets can live beside their pipeline declaration. Each manifest should include asset ID, kind, upstream source URLs, publication/version date, checksums, expected sizes, compatibility/consumers, and the immutable meta-assets S3 prefix. The publisher should materialize sources in temporary scratch, validate, upload the unpacked runtime directory and manifest, and never keep the large archive in the repo. This mirrors the existing Lambda-layer build pattern: resolve, download, assemble, validate, bundle/publish. Pulumi should expose the managed bucket and permissions or a small pointer, not perform the bulk remote download.

*Relevance: high*
*Context: Design discussion for remote pipeline asset publication*
*Tags: pipeline-assets manifest publisher s3 meta-assets pulumi*

---
*Observed: 2026-09-22T18:01:33.238Z*
