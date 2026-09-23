---
type: source
title: "Observation: Generic pipeline resource dependencies outweigh EFS-specific options"
tags:
  - pipeline
  - architecture
  - resource
  - dependencies
  - efs
  - nextflow
  - snakemake
  - taxprofiler
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-generic-pipeline-resource-dependencies-outweigh-efs-specific
relevance: critical
observed_at: 2026-09-18T15:21:42.954Z
source_context: "Issue #379 future-state architecture discussion"
---

# 🔴 Observation: Generic pipeline resource dependencies outweigh EFS-specific options

Desired future state for CAPE is framework-neutral pipeline resource dependencies: any well-formed Nextflow pipeline now, possible Snakemake later; zero or many mounted resources; resources may be databases or large shared datasets; physical volume IDs may change. This steers away from treating host-mounted EFS as the final architecture. The durable design should define a generic logical resource-dependency contract resolved at run time, with EFS attachment as one backend-specific executor adapter. Option 1 host-mounted EFS can remain a tactical bridge for the current Kraken2 path, but static host mounts do not naturally support arbitrary N resources or changing physical IDs. Option 2 direct ECS-managed child volumes is closer to the desired state but requires extending the Nextflow Batch executor or a generic CAPE task-submission layer. The canonical contract should not contain physical AWS IDs or database-specific assumptions.

*Relevance: critical*
*Context: Issue #379 future-state architecture discussion*
*Tags: pipeline architecture resource dependencies efs nextflow snakemake taxprofiler*

---
*Observed: 2026-09-18T15:21:42.954Z*
