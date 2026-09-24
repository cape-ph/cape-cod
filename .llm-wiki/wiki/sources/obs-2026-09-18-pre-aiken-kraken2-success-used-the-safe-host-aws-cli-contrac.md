---
type: source
title: "Observation: Pre-Aiken Kraken2 success used the safe host AWS CLI contract"
tags:
  - bactopia
  - kraken2
  - nextflow
  - aws
  - batch
  - cliPath
  - mount
  - regression
  - aiken
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-pre-aiken-kraken2-success-used-the-safe-host-aws-cli-contrac
relevance: critical
observed_at: 2026-09-18T14:46:14.548Z
source_context: "Historical pre-Aiken comparison for Issue #379"
---

# 🔴 Observation: Pre-Aiken Kraken2 success used the safe host AWS CLI contract

Historical source inspection resolved why pre-Aiken Batch Kraken2 runs did not hit the child mount failure. Before commit 83991c7, assets/containers/nextflow-kickstart/entrypoint.sh hard-coded aws.batch.cliPath=/home/ec2-user/miniconda/bin/aws. Nextflow 26.04.6 and nf-amazon mount the grandparent of cliPath into child containers, so this mounted /home/ec2-user/miniconda and preserved /usr/local. Commit 83991c7 changed the value to command -v aws inside the parent container, which returned /usr/bin/aws and caused the child /usr mount collision that hid /usr/local/env-execute and Wave entrypoints. The sibling aws-batch-ecs-ami repository's awsbatch profile installs the safe host CLI path via commit ea3623e. The older Bactopia v3 profile also supplied --aws_volumes, including host-path database/conda mounts, so previous success was an intentional compatible host-path contract rather than repeated luck. The v4 taxprofiler path initially lost both the safe host CLI path and the validated v3 Bactopia AWS volume/profile behavior.

*Relevance: critical*
*Context: Historical pre-Aiken comparison for Issue #379*
*Tags: bactopia kraken2 nextflow aws batch cliPath mount regression aiken*

---
*Observed: 2026-09-18T14:46:14.548Z*
