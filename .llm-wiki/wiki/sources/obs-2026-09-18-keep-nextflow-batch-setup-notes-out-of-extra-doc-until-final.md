---
type: source
title: "Observation: Keep Nextflow Batch setup notes out of extra-doc until finalized"
tags:
  - documentation
  - nextflow
  - batch
  - ami
  - efs
  - taxprofiler
  - scope
status: observation
created: 2026-09-18
updated: 2026-09-18
slug: obs-2026-09-18-keep-nextflow-batch-setup-notes-out-of-extra-doc-until-final
relevance: high
observed_at: 2026-09-18T14:55:50.827Z
source_context: "Issue #379 documentation boundary decision"
---

# ⭐ Observation: Keep Nextflow Batch setup notes out of extra-doc until finalized

The current extra-doc/README.nextflow-batch.md was a temporary decision-support draft for the Bactopia/taxprofiler EFS and AWS CLI analysis. It should not be checked in or treated as user-facing documentation. Once the host/child container, AWS CLI path, EFS attachment, database access, and resource contracts are settled, create a clean self-contained user-facing extra-doc that links to https://github.com/cape-ph/aws-batch-ecs-ami, does not mention the LLM Wiki, and omits manual launcher debugging details.

*Relevance: high*
*Context: Issue #379 documentation boundary decision*
*Tags: documentation nextflow batch ami efs taxprofiler scope*

---
*Observed: 2026-09-18T14:55:50.827Z*
