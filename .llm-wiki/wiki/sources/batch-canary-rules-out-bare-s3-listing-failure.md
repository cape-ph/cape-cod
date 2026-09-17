---
type: source
title: Batch canary rules out bare S3 listing failure
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: batch-canary-rules-out-bare-s3-listing-failure
---

# Batch canary rules out bare S3 listing failure

The corrected canary used the existing `ccd-pvsl-nextflow-jobdef:52`, workflow Batch queue, current container image, IAM role, and the same Batch host as the hung job. It completed in 15 seconds. AWS CLI listed the `pipeline-output/` prefix successfully, and Nextflow 25.10.4 with nf-amazon 3.4.4 completed a bare `file('s3://.../pipeline-output/').eachFile`, listing 24 directories including `kraken-debug-0`. Therefore the generic Batch network path, S3 permissions, current Nextflow S3 plugin, and bare `eachFile` operation are not sufficient to reproduce the hang.

The failure boundary is now narrower. Bactopia's `collect_samples` does more after the initial listing: it calls `item.isDirectory()`, then for the included sample calls `_is_sample_dir()` (`file("${dir}/${sample}").exists()`), and `_collect_inputs()` performs multiple S3-backed `.exists()` checks for QC files. A follow-up canary should reproduce those operations with explicit logging and a timeout, without invoking the AWS Batch executor. The same canary confirmed the kickstart image has AWS CLI at `/usr/bin/aws`, but the generated config's `/home/ec2-user/miniconda/bin/aws` path does not exist, leaving a separate likely child-submission problem.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
