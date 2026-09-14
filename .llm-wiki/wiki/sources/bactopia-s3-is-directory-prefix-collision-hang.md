---
type: source
title: Bactopia S3 isDirectory prefix collision hang
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: bactopia-s3-is-directory-prefix-collision-hang
---

# Bactopia S3 isDirectory prefix collision hang

The per-entry Batch canary isolated the hang to `item.isDirectory()` for `s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/pipeline-output/micah-test`. The canary completed the same operation for preceding entries, including `kraken-debug-0`; its sample directory, QC FASTQ, and QC report existence checks succeeded. It then stopped at `BEFORE_IS_DIRECTORY` for `micah-test` and was terminated after 180 seconds.

S3 has no object at `pipeline-output/micah-test` or `pipeline-output/micah-test/`, but it has 117 child objects below `pipeline-output/micah-test/`. The root also contains sibling prefixes `micah-test-2/`, `micah-test-3/`, and `micah-test-4/`. This creates a likely Nextflow 25.10.4/nf-amazon S3 directory metadata edge case: the name `micah-test` is a prefix of sibling directory names. Bactopia's `collect_samples` calls `item.isDirectory()` on every top-level item before checking the include list, so an unrelated prefix blocks the included `kraken-debug-0` sample. The earlier EC2 run on Nextflow 24.04.4 completed, which is consistent with a runtime/plugin behavior difference but does not by itself prove the old version's handling.

Potential remediation paths are to use a runtime that handles the S3 prefix collision correctly, change Bactopia's collection logic to avoid directory metadata checks on unrelated prefixes or filter included names earlier, or isolate the requested sample under a non-colliding input prefix. Do not delete or rename S3 data without explicit approval. The separate Batch image `cliPath` issue remains: `/usr/bin/aws` exists but `/home/ec2-user/miniconda/bin/aws` does not.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
