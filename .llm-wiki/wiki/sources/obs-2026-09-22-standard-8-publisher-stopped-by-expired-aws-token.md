---
type: source
title: "Observation: Standard-8 publisher stopped by expired AWS token"
tags:
  - pipeline-assets
  - publisher
  - aws-token
  - expired
  - standard8
  - s3
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-standard-8-publisher-stopped-by-expired-aws-token
relevance: high
observed_at: 2026-09-22T20:28:23.002Z
source_context: Standard-8 publication attempt
---

# ⭐ Observation: Standard-8 publisher stopped by expired AWS token

The Standard-8 publisher downloaded and extracted the upstream 5.95 GB archive successfully, then failed on the first S3 database upload with `ExpiredToken` because the temporary AWS session token expired during the long local download/validation phase. The publisher's TemporaryDirectory cleaned the local archive and extraction scratch, and the destination prefix `s3://ccd-meta-assets-vbkt-s3-8b7134e/pipelines/shared/databases/kraken2-bracken/standard-8/2026-06-26/` is empty. No asset was published and no taxprofiler run started. A future retry needs refreshed credentials; a stronger publisher should refresh or obtain credentials closer to upload time, or run the publisher in an AWS-hosted job.

*Relevance: high*
*Context: Standard-8 publication attempt*
*Tags: pipeline-assets publisher aws-token expired standard8 s3*

---
*Observed: 2026-09-22T20:28:23.002Z*
