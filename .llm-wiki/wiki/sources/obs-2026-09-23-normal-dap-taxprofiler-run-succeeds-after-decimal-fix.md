---
type: source
title: "Observation: Normal DAP taxprofiler run succeeds after Decimal fix"
tags:
  - issue-379
  - dap
  - taxprofiler
  - kraken2
  - decimal
  - batch
  - s3
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-normal-dap-taxprofiler-run-succeeds-after-decimal-fix
relevance: critical
observed_at: 2026-09-23T15:30:25.051Z
source_context: Post-deployment normal DAP validation
---

# 🔴 Observation: Normal DAP taxprofiler run succeeds after Decimal fix

After the Lambda deployment, the normal DAP invocation for Taxprofiler Kraken2 returned HTTP 200 and submitted parent 231f62f2-9dbd-4540-b92d-b448252e5025. Parent workflow, Kraken2 child bdeccf8a-9390-4012-b505-10f21d1fbc66, and MultiQC child 57c1eb2a-81bf-4569-b9b5-dfaed790673a all finished with AWS Batch SUCCEEDED and exit code 0. Kraken2 requested 2 vCPUs and 9216 MiB, used the analysis queue, and had only the aws-cli host volume, no EFS mount. Output prefix s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/taxprofiler-dap-standard8-rerun-20260923152141/ contains the Kraken2 report, MultiQC report, and pipeline metadata. The synthetic one-read report is 100% unclassified, but the workflow completed successfully. The test prefix is retained pending cleanup approval.

*Relevance: critical*
*Context: Post-deployment normal DAP validation*
*Tags: issue-379 dap taxprofiler kraken2 decimal batch s3*

---
*Observed: 2026-09-23T15:30:25.051Z*
