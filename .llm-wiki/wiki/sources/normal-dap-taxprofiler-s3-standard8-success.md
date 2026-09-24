---
type: source
title: Normal DAP taxprofiler S3 Standard-8 success
status: insight
category: validation
created: 2026-09-23
updated: 2026-09-23
slug: normal-dap-taxprofiler-s3-standard8-success
---

# Normal DAP taxprofiler S3 Standard-8 success

The deployed Decimal serialization fix unblocked the normal DAP path. Invoking the deployed submit handler for `Taxprofiler Kraken2` 2.0.1 with the published Standard-8 database sheet returned HTTP 200 and submitted parent `231f62f2-9dbd-4540-b92d-b448252e5025`. The Nextflow parent, Kraken2 child `bdeccf8a-9390-4012-b505-10f21d1fbc66`, and MultiQC child `57c1eb2a-81bf-4569-b9b5-dfaed790673a` all ended with AWS Batch `SUCCEEDED` and exit code 0. The Kraken2 child requested 2 vCPUs and 9216 MiB, ran on the analysis queue, and used only the host AWS CLI volume, not EFS. The isolated output prefix contains the Kraken2 report, MultiQC report, and pipeline metadata. The one-read synthetic report is 100% unclassified, but the end-to-end workflow succeeded. Related tracking: [[sources/obs-2026-09-23-normal-dap-taxprofiler-run-succeeds-after-decimal-fix]].

*Category: validation*

---
*Captured: 2026-09-23*

## Related

_Add links to related pages._
