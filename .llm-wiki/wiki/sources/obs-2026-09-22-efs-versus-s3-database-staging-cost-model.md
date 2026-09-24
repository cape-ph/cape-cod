---
type: source
title: "Observation: EFS versus S3 database staging cost model"
tags:
  - issue-379
  - aws
  - efs
  - s3
  - cost
  - performance
  - taxprofiler
  - staging
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-efs-versus-s3-database-staging-cost-model
relevance: high
observed_at: 2026-09-22T15:11:26.570Z
source_context: Cost comparison for shared Kraken2 database
---

# ⭐ Observation: EFS versus S3 database staging cost model

For us-east-2 pricing checked 2026-09-22: EFS Regional Standard storage is $0.30/GB-month and this file system uses Elastic Throughput, priced at $0.03/GB read and $0.06/GB write. S3 Standard storage is $0.023/GB-month; PUT/COPY/POST/LIST is $0.005/1,000 requests and GET is $0.0004/1,000 requests. With N decimal GB, R one-hour runs/month, and identical S3 staging, the EFS-source estimate is `0.30*(N+1) + 0.03*N*R + 0.023*N*(R/720)` plus S3 request costs and any cross-AZ transfer. The S3-source estimate is `0.023*N + 0.023*N*(R/720)` plus S3 request costs, assuming same-region S3 transfer. For the observed 8.584 GB database, this is about $2.88/month EFS storage plus $0.258 per run of EFS elastic reads versus $0.197/month S3 canonical storage; one-hour transient stage storage is about $0.00027/run. Compute costs cancel under the same-instance assumption. Current EFS is a 189.9 GB Regional General Purpose Elastic file system, so the N+1 figure is a standalone incremental model; if EFS remains for other databases, only marginal bytes should be charged. A same-region S3-backed database likely removes EFS storage, EFS read charges, mounter/SG/AMI dependencies, and may make the source-to-stage leg faster, but it does not eliminate the per-task S3 stage under the current Nextflow path-input model.

*Relevance: high*
*Context: Cost comparison for shared Kraken2 database*
*Tags: issue-379 aws efs s3 cost performance taxprofiler staging*

---
*Observed: 2026-09-22T15:11:26.570Z*
