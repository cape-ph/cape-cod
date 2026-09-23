---
type: source
title: "Observation: Fusion ruled out by Seqera platform dependency"
tags:
  - issue-379
  - architecture
  - fusion
  - seqera
  - nextflow
  - staging
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-fusion-ruled-out-by-seqera-platform-dependency
relevance: high
observed_at: 2026-09-22T15:01:22.179Z
source_context: Owner design constraint update
---

# ⭐ Observation: Fusion ruled out by Seqera platform dependency

Owner ruled out Fusion as a solution if it requires Seqera Platform access or cost; CAPE exists in part to avoid that dependency. The design space therefore excludes third-party forks, shared EFS work directories, and Seqera-dependent Fusion. The remaining work is to evaluate a CAPE-owned runtime/configuration approach or accept the current isolated S3 staging. A possible experimental but unsupported route is using database-sheet parameters to override the generated Kraken2 `--db` path while supplying a small placeholder `db_path`; this is not a production recommendation and would need a contained test because the pipeline still declares the database as a Nextflow `path` input and duplicate `--db` option behavior is uncertain.

*Relevance: high*
*Context: Owner design constraint update*
*Tags: issue-379 architecture fusion seqera nextflow staging*

---
*Observed: 2026-09-22T15:01:22.179Z*
