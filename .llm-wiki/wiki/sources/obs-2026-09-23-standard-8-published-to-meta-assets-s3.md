---
type: source
title: "Observation: Standard-8 published to meta-assets S3"
tags:
  - pipeline-assets
  - standard8
  - s3
  - publisher
  - aws-batch
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-standard-8-published-to-meta-assets-s3
relevance: critical
observed_at: 2026-09-23T11:30:44.682Z
source_context: Verified AWS-hosted Standard-8 publication
---

# 🔴 Observation: Standard-8 published to meta-assets S3

AWS-hosted Python 3.12 Batch publisher job `13ad2089-868d-4aa5-8a63-72a03b08c535` successfully published the immutable Standard-8 asset using role-based credentials. Prefix: `s3://ccd-meta-assets-vbkt-s3-8b7134e/pipelines/shared/databases/kraken2-bracken/standard-8/2026-06-26/`. Validation found 17 database files totaling 8,638,898,739 bytes; all 17 upstream MD5 values matched; archive MD5 was `7685f43cce057c2ca18511c925399b72`; manifest and database objects use AES256. The generated manifest records per-file MD5/SHA256 and sizes. Temporary bundle bucket `pipeline-asset-pub-20260923111327` and temporary job-definition revisions were removed. No taxprofiler run or further deployment was started.

*Relevance: critical*
*Context: Verified AWS-hosted Standard-8 publication*
*Tags: pipeline-assets standard8 s3 publisher aws-batch*

---
*Observed: 2026-09-23T11:30:44.682Z*
