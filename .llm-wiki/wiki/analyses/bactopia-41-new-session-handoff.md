---
type: analysis
title: Bactopia 4.1 new-session handoff
created: 2026-09-16
updated: 2026-09-23
status: historical
---

# Bactopia 4.1 new-session handoff

This is a historical handoff. Current status is recorded in
`analyses/issue-379-migration-resumption-handoff.md`, as of commit `abad135`.
The sections below retain the earlier historical handoff and are superseded where
that current page differs.

Status: paused after validation and design preparation. The design was revised
with owner feedback on scope, dynamic AWS resource resolution, two-layer
pipeline/Nextflow configuration, QC policy, output-contract adapters, dev-only
Pulumi changes, and CAPE-owned run metadata. No Bactopia v4 production DAG, ETL,
Pulumi, or frontend implementation changes have been made. The next session
should start from the design document and the findings report, not from the
older v3 assumptions.

## Read first

1. [[analyses/bactopia-41-cape-cod-implementation-design]]
2. [[analyses/kraken2-and-bactopia-41-migration-findings]]
3. [[analyses/aiken-demo-platform-generalization-review]]
4. [[analyses/bactopia-41-ec2-validation-handoff]]

The implementation design is the primary handoff for file-level work. The
findings report is the primary evidence record. The older EC2 handoff contains
historical commands and should be read for context only; some of its early
status statements predate the final m5.large validation.

## Current conclusion

Bactopia v4.1 is the migration target. New production runs should use a v4-only
ETL and DAG contract. The old v3 definitions and historical outputs should
remain readable for rollback and historical access, but the new runtime should
not silently support two incompatible result schemas.

The normal Bactopia v4.1 workflow completed with `--skip_qc_plots true` on
Nextflow 26.04.6. The default no-skip QC path did not finish in the tested
bound:

- The post-resize parent run lasted 1h54m44s.
- QC child job `d11ca863-0b4f-479a-a565-c8d3411a4b96` requested 4 vCPU and 8,192
  MiB.
- The child was still running when the parent timeout terminated it.
- It ended with exit code 143 and status reason `Job killed by NF`.
- Original NanoPlot artifacts were present, but final QC output was absent.
- The m5.large launcher remained healthy, with no new kernel OOM evidence.
- No orphaned Batch jobs remained after termination.

The current decision is whether production should increase the QC child
resources, allow a longer runtime, or make plot skipping an explicit policy. The
skip-plots run is not evidence that default NanoPlot QC is acceptable.

## Validated results

- Nextflow 26.04.6 and nf-amazon 3.9.2 are deployed in Batch job definition
  revision `55` with image digest
  `sha256:df5f867edf959b0dd31874d726a2cbe9ed531dfebed4e03d453f371119a2af80`.
- The original S3 prefix-collision hang is fixed by the deployed runtime.
- The kickstart entrypoint discovers the AWS CLI path with `command -v aws` and
  writes the S3 work prefix below `s3://nextflow-spot-batch-temp-<jobid>/work`.
- The deployed entrypoint smoke job submitted and completed a child Batch job.
- The EC2 launcher was restored to its original `t3.micro` size after testing.
  It is currently running. The test-only symlink
  `/home/ec2-user/miniconda/bin/aws -> /usr/bin/aws` remains in place.
- Standalone Kraken2 succeeded with the v4 ONT QC input when the canary used an
  explicit ECS-managed EFS mount. The persisted report is at:

    ```text
    s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/bactopia41-ec2-20260915143928/standalone-efs-canary-v4/v4-report.txt
    ```

- The v3 and standalone v4 Kraken2 reports have the same 360-row count, taxid
  set, and classification totals. They differ in rank codes and low-count row
  ordering. The existing parser and HTML renderer handled the v4 report.
- The Bactopia v4 Kraken2 wrapper is not usable as-is for this ONT/S3 workflow.
  Its input plugin did not resolve the S3 Bactopia path, and its Kraken2 module
  ignored the ONT `lr` slot and generated `--paired null null`.
- The results ETL is partly compatible with v4. AMRFinderPlus, assembler,
  Sourmash, and MASH shapes are usable. V4 merged MLST is headered and requires
  a v4-only parser/schema. V4 normal output did not publish the old
  `software-versions/software_versions.yml` manifest required by current report
  joins.

## Current implementation direction

The implementation design keeps the taxonomic profiler decision open between
`nf-core/taxprofiler` and a new standalone Kraken2 Nextflow wrapper. The chosen
component must:

- accept `main/qc/<sample>_ONT.fastq.gz`;
- run on the shared CAPE Nextflow runtime configuration;
- access the Kraken2 database through an approved EFS or staging strategy;
- publish the canonical report path `tools/kraken2/<sample>.kraken2.report.txt`;
- produce a stable six-column Kraken2 report whose semantic contents pass the
  existing parser and renderer checks.

The first implementation should attempt one shared generated Nextflow config for
all CAPE Nextflow DAPs. Pipeline profiles should carry pipeline-specific options
while the shared config carries AWS Batch execution settings. A
pipeline-specific config override requires an explicit design decision and owner
approval.

Do not implement the Bactopia v4 Kraken2 wrapper as the default path unless the
upstream S3 and ONT `lr` issues are resolved and a production-shaped test
passes.

## Repository state

- Repository: `cape-cod`.
- Branch: `aiken_demo`.
- Last committed infrastructure fix:
  `83991c7 fix(nextflow): resolve batch runtime and s3 path issues`.
- The authored findings, handoff, source observations, and this design/handoff
  work are uncommitted by project convention. Do not commit unless the owner
  asks for a commit.
- `PLAN.md` remains an untracked Pantheon/deepwork artifact and must remain
  uncommitted.
- The current working tree contains authored wiki pages and deepwork progress;
  inspect `git status` before editing code.

## Important current files

CAPE Cod pipeline profile fixtures:

- `assets/analysis-pipelines/bactopia/bactopia-base-3.2.0.json`
- `assets/analysis-pipelines/bactopia/bactopia-base-dev.json`
- `assets/analysis-pipelines/bactopia/ont-bactopia-3.2.0.json`
- `assets/analysis-pipelines/bactopia/ont-bactopia-dev.json`
- `assets/analysis-pipelines/bactopia/kraken2-bactopia-3.2.0.json`
- `assets/analysis-pipelines/bactopia/kraken2-bactopia-dev.json`

Runtime and data files:

- `assets/containers/nextflow-kickstart/Dockerfile`
- `assets/containers/nextflow-kickstart/entrypoint.sh`
- `assets/etl/etl_bactopia_results.py`
- `assets/etl/etl_bactopia_samples.py`
- `assets/report/bactopia-single-sample-analysis/data_function.py`
- `Pulumi.cape-cod-dev.yaml`
- `Pulumi.cape-cod-public.yaml`

The external Airflow Bactopia/Kraken DAG repository is not checked out in this
workspace. Its exact repository name, owner, branch, and DAG files must be
confirmed before editing. CAPE Cod owns the MWAA environment deployment and
configuration in its dev Pulumi config; the external DAG repository or
`cape-cod-env` path owns DAG source publication and synchronization details.

## Required next-session order

1. Read this handoff, the implementation design, and the findings report.
2. Confirm the external Airflow DAG repository and inspect its v3.2.0 Bactopia
   and Kraken stages.
3. Decide between `nf-core/taxprofiler` and a standalone wrapper. Resolve the
   database access strategy at the same time.
4. Implement the v4 pipeline profile contract and tests in CAPE Cod. Do not
   delete the v3 fixtures yet.
5. Implement the v4-only MLST and software metadata ETL contract with fixtures.
6. Run the dev-only integration path through Bactopia, the selected profiler,
   Glue ETL/crawlers, report joins, and HTML rendering.
7. Run `pulumi preview --diff` against the target stack. Reconcile every action
   before the owner performs a deploy.
8. Update the external Airflow DAG repository only after the CAPE contract and
   selected profiler are stable.

## Safety constraints

- Never run `pulumi up`, deploy, or destroy resources without explicit owner
  approval.
- Keep all test S3/EFS work below the existing scratch root until cleanup is
  separately approved.
- Do not delete scratch data, old pipeline fixtures, or external resources as
  part of implementation.
- Return the EC2 launcher to `t3.micro` after any future test session.
- Do not treat the EC2 Miniconda AWS CLI symlink as a production requirement.
- Do not use byte-for-byte Kraken2 report equality as an acceptance gate; use
  semantic row, taxid, totals, parser, and renderer checks.
