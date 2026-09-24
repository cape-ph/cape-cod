---
type: source
title: "Observation: Taxprofiler docs define database paths as Nextflow path inputs"
tags:
  - issue-379
  - nf-core-taxprofiler
  - nextflow
  - efs
  - staging
  - database-sheet
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-taxprofiler-docs-define-database-paths-as-nextflow-path-inpu
relevance: high
observed_at: 2026-09-22T14:30:06.411Z
source_context: Taxprofiler v2.0.1 docs and source review during EFS path probe
---

# ⭐ Observation: Taxprofiler docs define database paths as Nextflow path inputs

nf-core/taxprofiler v2.0.1 usage docs say `db_path` may be an uncompressed directory or a `.tar.gz` archive. The workflow sends uncompressed database paths through `ch_final_dbs` directly to the profiling subworkflow, and the bundled Kraken2 module declares the database as a Nextflow `path db` input and runs `kraken2 --db $db`. The CLI has no documented EFS/cache/no-staging option. `--save_untarred_databases` only publishes decompressed archive outputs. This makes Nextflow AWS Batch path staging, rather than a taxprofiler-specific copy option, the leading explanation for the S3 stage tree.

*Relevance: high*
*Context: Taxprofiler v2.0.1 docs and source review during EFS path probe*
*Tags: issue-379 nf-core-taxprofiler nextflow efs staging database-sheet*

---
*Observed: 2026-09-22T14:30:06.411Z*
