---
type: source
title: "Observation: Taxprofiler S3 sheet probe reached child runtime mount failure"
tags:
  - taxprofiler
  - bactopia
  - nextflow
  - batch
  - s3
  - efs
  - mount
  - cliPath
  - runtime
status: observation
created: 2026-09-17
updated: 2026-09-17
slug: obs-2026-09-17-taxprofiler-s3-sheet-probe-reached-child-runtime-mount-failu
relevance: critical
observed_at: 2026-09-17T19:09:17.116Z
source_context: "Issue #379 first taxprofiler sheet-resolution probe"
---

# 🔴 Observation: Taxprofiler S3 sheet probe reached child runtime mount failure

The first AWS Batch taxprofiler v2.0.1 probe used the deployed Nextflow 26.04.6 kickstart job definition and direct S3 paths for both --input and --databases. The initial run failed validation because the ONT input sheet had an empty run_accession; after correcting it, taxprofiler accepted the S3 sheet paths, parsed the database row, and submitted UNTAR and FASTQC child jobs. The child jobs failed before database processing: the Wave coreutils image could not start /usr/local/bin/_entrypoint.sh, and the FastQC image could not start /usr/local/env-execute. The parent runtime resolved AWS_CLI_PATH=/usr/bin/aws, so this is consistent with the known dynamic-child /usr host-path mount collision rather than a database or sheet failure. No database mount or S3 database staging behavior has been tested yet. The failed parents left temporary work buckets nextflow-spot-batch-temp-898ebe80-104d-4d7a-9c26-08a751cc5cca and nextflow-spot-batch-temp-05a14f70-4ac6-4ac8-823e-dbd5dc4e6b2a; they were not deleted.

*Relevance: critical*
*Context: Issue #379 first taxprofiler sheet-resolution probe*
*Tags: taxprofiler bactopia nextflow batch s3 efs mount cliPath runtime*

---
*Observed: 2026-09-17T19:09:17.116Z*
