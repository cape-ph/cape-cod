---
type: source
title: "Observation: Design constraints for avoiding shared database staging"
tags:
  - issue-379
  - architecture
  - nextflow
  - fusion
  - efs
  - staging
  - concurrency
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-design-constraints-for-avoiding-shared-database-staging
relevance: high
observed_at: 2026-09-22T14:56:01.905Z
source_context: Design discussion after minimal EFS staging probe
---

# ⭐ Observation: Design constraints for avoiding shared database staging

Owner ruled out maintaining a fork of nf-core/taxprofiler or other third-party pipeline code. A single shared EFS work path is also not acceptable as a production design because it couples concurrent runs, risks scratch collisions and cleanup failures, and a 10 GiB EFS volume would leave little room beside the roughly 8 GiB database. The shared read-only database mount must remain distinct from per-run work storage. Fusion is the leading no-fork candidate to compare, but it would likely require an S3-backed database path rather than the current EFS path, plus Fusion/Wave runtime support and a valid Seqera Platform access token. It preserves S3 workdir isolation and may avoid full path staging, but introduces subscription/token, compatibility, S3 random-read, caching, and operational costs. Current taxprofiler CLI options do not control this: `--databases` supplies a sheet whose `db_path` becomes a Nextflow `path db` input; `--save_untarred_databases` is unrelated. No design decision has been made.

*Relevance: high*
*Context: Design discussion after minimal EFS staging probe*
*Tags: issue-379 architecture nextflow fusion efs staging concurrency*

---
*Observed: 2026-09-22T14:56:01.905Z*
