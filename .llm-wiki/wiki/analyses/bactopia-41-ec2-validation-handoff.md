---
type: analysis
title: Bactopia 4.1 EC2 validation handoff
created: 2026-09-15
updated: 2026-09-23
status: historical
---

# Bactopia 4.1 EC2 validation handoff

Status: historical EC2 validation record. The current Issue 379 checkpoint is
in [[analyses/issue-379-migration-resumption-handoff]]. The EC2 findings remain
useful evidence for Bactopia v4 behavior, but EFS host/bootstrap ownership is
tracked with PR 385 and issues 381/380.

## Current confirmed infrastructure

- Production Batch image is deployed and validated:
  - Active job definition: `ccd-pvsl-nextflow-jobdef:55`
  - Image digest: `sha256:df5f867edf959b0dd31874d726a2cbe9ed531dfebed4e03d453f371119a2af80`
  - Nextflow: 26.04.6
  - nf-amazon: 3.9.2
- `assets/containers/nextflow-kickstart/entrypoint.sh` derives the AWS CLI path with `command -v aws`.
- The entrypoint uses an S3 work prefix: `s3://nextflow-spot-batch-temp-<jobid>/work`.
- The deployed actual-entrypoint smoke test succeeded. Child Batch job `3e4df4c1-cbd8-48ae-b554-8c9168fc6b05` completed successfully.
- The original S3 prefix collision is fixed. Nextflow 26.04.6 resolves `micah-test` despite siblings `micah-test-2`, `micah-test-3`, and `micah-test-4`.
- Code and authored wiki findings were committed and pushed as `83991c7 fix(nextflow): resolve batch runtime and s3 path issues` on branch `aiken_demo`. `PLAN.md` remains untracked by project convention.

## EC2 test instance

- Instance: `i-01274bddc155993e8`
- Private IP: `10.0.135.10`
- Type: `t3.micro`, approximately 1 GiB RAM
- AMI: `ami-0d244966929712cb6`
- Existing runtime: Nextflow 24.04.4, Java 21, AWS CLI at `/usr/bin/aws`
- Shared data mount: `/mnt/nextflow_shared_data`
- Kraken2 database: `/mnt/nextflow_shared_data/kraken2`
- Last AWS status: instance reachability failed since `2026-09-15T20:09:00Z`; system and EBS reachability passed.
- EC2 console output recorded a Linux OOM event killing a Java process. SSH also timed out during the Bactopia v4.1 QC resume.
- Recommended action: restore reachability and resize to at least `t3.medium`; `t3.large` is safer for a long Nextflow launcher run. Do not trust v4 QC timing until this is done.
- Test-only symlink created on EC2: `/home/ec2-user/miniconda/bin/aws -> /usr/bin/aws`. It prevents Nextflow from mounting host `/usr` into Biocontainer child jobs. Historical child jobs used the `/home/ec2-user/miniconda` mount successfully.

## Test input

- Local source: `/home/lp76/projects/cape/test-data/seqauto/caerbannog-test-sequencing-reads/sequencing`
- 41 ONT FASTQ.GZ shards.
- Concatenated in numeric filename order to 121,819,231 bytes and 29,669 reads.
- Local concatenated SHA256: `1f6f3680679474e123d151ec0348bc2e33bc190b83798303ca4c3c8c47d119c4`
- Uploaded input: `s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/bactopia41-ec2-20260915143928/input/caerbannog-test.fastq.gz`
- Local `meta.json` sample ID: `caerbannog-test`.
- FASTQ headers contain `sample_id=Ecoli`.
- Version-distinguishing output sample names used:
  - v3 baseline: `caerbannog-test-nf2404-bt320`
  - v4 candidate: `caerbannog-test-nf2604-bt410`
- `assets/etl/etl_seqarchive.py` confirms production behavior: sorted `sequencing/` members are concatenated into one `sequencing-reads.gz`; individual split files and a manifest are also retained.

## Tests and results

### v3.2.0 baseline

- Initial attempt with `/usr/bin/aws` failed because Nextflow mounted host `/usr` into child containers, hiding `/usr/local/env-execute`.
- EC2 symlink plus `/home/ec2-user/miniconda/bin/aws` allowed child containers to start.
- v3.2 baseline2 produced core Bactopia outputs, including assembler/QC/report artifacts, but exited unsuccessful at `BACTOPIA:DATASETS` because the expected `v3.2.0/amrfinderplus.tar.gz` output was missing even though the URL is reachable manually. Work and output root: `s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/bactopia41-ec2-20260915143928/v3.2.0-baseline2/`.
- Historical v3 QC child completed in approximately 2.6 minutes on the same data.

### v4.1.0 candidate

- Bactopia v4.1.0 requires Nextflow `>=26.04.0`; use the separately installed EC2 Nextflow 26.04.6 binary at `$HOME/nextflow-runtimes/26.04.6/nextflow`.
- `-profile aws` is not defined in v4.1.0. Use `-profile docker` plus a temporary config setting `process.executor=awsbatch`, the analysis queue, `/home/ec2-user/miniconda/bin/aws`, and the EFS/conda volumes.
- v4 first reached DATASETS and GATHER after setting `BACTOPIA_CACHEDIR` to an S3 scratch prefix. The default local cache caused S3 `AccessDenied` behavior in AWS Batch.
- Default v4 QC child `c570c615-e7d1-4825-aab7-2f9d055af8e2` ran approximately 85 minutes, produced original NanoPlot outputs, and was killed with exit 143 when the bounded SSH test ended. No intrinsic QC error was captured; final QC output was absent.
- QC source comparison: v3.2 and v4.1 perform the same main ONT phases: nanoq filtering, skip ONT error correction, skip coverage reduction with genome size zero, pre/post fastq-scan, original/final NanoPlot, and final checks. V4 refactors the module, uses `bactopia-check-fastqs` instead of v3 `check-fastqs.py`, and changes supplemental/output organization.
- The `--skip_qc_plots` resume was started as background task `bg-23` but lost SSH when the EC2 instance became unreachable. It produced no usable result and has not been repeated since the EC2 issue.

## Next actions

1. Restore EC2 reachability and resize the launcher instance.
2. Verify SSH, memory, swap, and that no stale Nextflow process remains.
3. Resume v4.1 from the existing S3 work directory with `--skip_qc_plots true` and a longer bound. Reuse DATASETS/GATHER; do not restart from scratch.
4. If QC completes, inspect v4 Bactopia output layout and report files.
5. Run Kraken2 through Bactopia v3 and v4 against their respective outputs.
6. Compare output contracts, not byte-for-byte files:
   - QC gate path `<outdir>/<sample>/main/qc/<sample>.fastq.gz`.
   - Current DAG Kraken report path `<outdir>/<sample>/tools/kraken2/<sample>.kraken2.report.txt`.
   - Bactopia metadata, assembler, annotation, reports, and logs.
   - Kraken report columns and the existing HTML parser/rendering path.
7. Keep all run outputs under the `batch_job_scratch/bactopia41-ec2-20260915143928/` root until comparison is complete. Do not delete scratch data without explicit approval.

## Current blockers and conclusions

- The S3 prefix collision, Docker DNS, Nextflow 26.04 deployment, AWS CLI path, and S3 work-prefix fixes are complete and validated in deployed Batch canaries.
- Bactopia v3.2.0 is incompatible with Nextflow 26.04.6 due `nextflow.util.SysHelper`, so v4.1 is the correct migration direction.
- The current blocking factor for EC2 testing is the t3.micro's failed reachability and OOM history, not yet a confirmed Bactopia v4 QC defect.
