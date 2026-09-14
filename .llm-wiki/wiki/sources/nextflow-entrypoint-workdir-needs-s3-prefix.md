---
type: source
title: Nextflow entrypoint workdir needs S3 prefix
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: nextflow-entrypoint-workdir-needs-s3-prefix
---

# Nextflow entrypoint workdir needs S3 prefix

The actual deployed entrypoint smoke confirmed the dynamic CLI path: it logged `AWS_CLI_PATH=/usr/bin/aws` and launched Nextflow 26.04.6. It then failed before child submission with `Creating a bucket is not supported` because the entrypoint passes the root of its temporary S3 bucket as `-work-dir s3://nextflow-spot-batch-temp-<jobid>`. An earlier explicit-config canary using `/usr/bin/aws` and an existing S3 subprefix submitted child Batch job `12dba23c-0177-4ccf-89f5-faf6106fc9f6`, so the CLI path itself works. Proposed next fix: change the entrypoint work directory to `s3://${BUCKET_TEMP_NAME}/work` (and optionally cache paths to subprefixes), then rebuild/deploy and rerun the actual entrypoint smoke. This is a new code/deploy change, not yet applied.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
