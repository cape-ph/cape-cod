---
type: source
title: Original Bactopia Dragonflye zero-genome-size failure
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: original-bactopia-dragonflye-zero-genome-size-failure
---

# Original Bactopia Dragonflye zero-genome-size failure

The original Bactopia CloudWatch stream `ccd-pvsl-nextflow-jobdef/default/4a607e19d09f4353bdd71772411273bb` contains a real process failure, not merely an ECS essential-container shutdown. `BACTOPIA:ASSEMBLER:ASSEMBLER_MODULE (kraken-debug-0)` failed four retries in `quay.io/biocontainers/bactopia-assembler:1.0.4--hdfd78af_0`. Dragonflye processed the single-end `kraken-debug-0.fastq.gz`, saw 7 reads and 116,576,080 total bases, then KMC found zero unique k-mers and zero counted k-mers. Dragonflye estimated genome size 0 bp and exited with `Illegal division by zero at /usr/local/bin/dragonflye line 234`.

This is a deterministic sample-data failure. It is independent of the Nextflow S3 prefix collision and AWS Batch infrastructure. The Kraken2 branch can still proceed if the QC output gate is satisfied, but the Bactopia branch/report will fail for this tiny debug input unless the input is replaced or assembly is deliberately skipped/configured around. The work directory was `s3://nextflow-spot-batch-temp-2d2dff93-4318-405c-8cd9-1b137418098c/cc/7fe9cdce9d8b7a8312b206f20e2aae/`.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
