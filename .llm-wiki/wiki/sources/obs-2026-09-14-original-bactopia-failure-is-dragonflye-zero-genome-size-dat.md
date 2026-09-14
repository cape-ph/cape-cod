---
type: source
title: "Observation: Original Bactopia failure is Dragonflye zero-genome-size data failure"
tags:
  - bactopia
  - dragonflye
  - assembler
  - kraken2
  - data
  - failure
  - aws
  - batch
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-original-bactopia-failure-is-dragonflye-zero-genome-size-dat
relevance: high
observed_at: 2026-09-14T18:23:45.091Z
source_context: Diagnosis of original Bactopia Batch failure
---

# ⭐ Observation: Original Bactopia failure is Dragonflye zero-genome-size data failure

CloudWatch stream `ccd-pvsl-nextflow-jobdef/default/4a607e19d09f4353bdd71772411273bb` contains the actionable Bactopia failure. `BACTOPIA:ASSEMBLER:ASSEMBLER_MODULE (kraken-debug-0)` retried four times and failed in container `quay.io/biocontainers/bactopia-assembler:1.0.4--hdfd78af_0`. The single-end input was `kraken-debug-0.fastq.gz`; Dragonflye saw 7 reads, 116,576,080 total bases, average length 2,227, but KMC found zero unique k-mers and zero counted k-mers, so estimated genome size was 0 bp. Dragonflye then exited with `Illegal division by zero at /usr/local/bin/dragonflye line 234`. This is a deterministic input/data failure, not an AWS Batch, Nextflow S3, or container infrastructure failure. It explains the vague essential-container error. The DAG's Kraken2 branch can still be independently tested because it gates on QC output, but the Bactopia branch/report will fail for this tiny debug sample unless the input is replaced or Bactopia is configured to skip assembly.

*Relevance: high*
*Context: Diagnosis of original Bactopia Batch failure*
*Tags: bactopia dragonflye assembler kraken2 data failure aws batch*

---
*Observed: 2026-09-14T18:23:45.091Z*
