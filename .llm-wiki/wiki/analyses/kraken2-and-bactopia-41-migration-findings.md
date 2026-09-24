---
type: analysis
title: Kraken2 and Bactopia 4.1 migration findings
created: 2026-09-16
updated: 2026-09-23
status: current-findings
---

# Kraken2 and Bactopia 4.1 migration findings

Status: current findings record as of commit `abad135`. The deployed
Nextflow/Batch infrastructure fixes, Bactopia v4 ETL contract slice, selected
`nf-core/taxprofiler` route, and normal DAP plumbing are validated. The
remaining acceptance gate is representative Bactopia -> taxprofiler -> ETL ->
report validation and the v4 crawlable run-metadata sidecar.

## Current checkpoint

- Bactopia v4.1 is the new-run target; v3 remains historical/rollback data.
- Bactopia's integrated v4 Kraken2 ONT path is not the production route because it ignores the `lr` input slot.
- `nf-core/taxprofiler` v2.0.1 is the selected separate Kraken2 route.
- The normal DAP path succeeded with a synthetic one-read input. Representative Kraken2 report evidence exists from the standalone canary.
- ETL and report compatibility are in this repository and remain part of Issue 379 acceptance.
- EFS-specific implementation details are mixed historical evidence; the capability implementation itself belongs to PR 385 and issues 381/380.

## Executive summary

The original Kraken2 hang was not caused by IAM permissions, the S3 bucket, or
generic AWS Batch networking. Nextflow 25.10.4/nf-amazon 3.4.4 hangs during S3
directory metadata resolution when a directory name is a prefix of sibling
directories. The production output root contains `micah-test/`, `micah-test-2/`,
`micah-test-3/`, and `micah-test-4/`. Bactopia scans all top-level entries
before applying its include filter, so the unrelated `micah-test` entry blocked
the requested sample.

The production image was moved to Nextflow 26.04.6, which contains the upstream
S3 lookup fix. The fix was validated against the original production-shaped S3
root and then deployed. The deployed entrypoint smoke test also validated the
dynamic AWS CLI path and S3 work-prefix behavior, including successful
submission and completion of a child AWS Batch job.

Bactopia v3.2.0 cannot run under Nextflow 26.04.6 because its configuration
imports `nextflow.util.SysHelper`. Bactopia v4.1.0 requires Nextflow
`>=26.04.0`, so the team is evaluating a Bactopia 4.1 migration rather than
maintaining a custom intermediate runtime.

Bactopia v4.1 normal processing completed on the EC2 test lane using the proven
input set, Nextflow 26.04.6, Docker profile, S3 cache, and `--skip_qc_plots`.
Its QC output layout differs from v3.2.0. A separate post-resize no-skip QC
validation was bounded at 1h54m and did not complete, so the full QC path is not
treated as equivalent to the skip-plots result. The v4.1 Kraken2 tool currently
has separate integration issues: it does not accept the S3 Bactopia output path
through its input plugin, and it ignores ONT reads represented in the `lr` slot,
generating `null null --paired`. A standalone Kraken2 process is being tested to
separate Kraken2/container/database behavior from Bactopia's tool wrapper.

## Leadership summary

- The original production blocker is understood and fixed in the deployed
  Nextflow runtime.
- The new Bactopia 4.1 normal workflow has completed successfully on
  representative ONT data.
- A successful Bactopia 4.1 run does not yet imply that the current
  Kraken2-through-Bactopia integration is migration-ready.
- The likely strategic direction is to run Kraken2 as a separate Nextflow
  component rather than patching Bactopia's v4.1 Kraken2 tool.
- The remaining risks are integration and output-contract risks, not the
  original S3 hang:
    - analysis-host EFS availability for child Batch jobs;
    - v4.1 tool-specific handling of S3 Bactopia output and ONT inputs;
    - full QC runtime and resource requirements;
    - changed QC/output paths and report assumptions;
    - cross-repository DAG, ETL, and report migration work.
- No production DAG or Pulumi changes have been made for the migration. The
  deployed infrastructure fix was committed as `83991c7` on `aiken_demo`.

## Original failure and root cause

The original parent log stopped after:

```text
Including 1 samples for analysis
```

and never emitted:

```text
Found 1 samples to process
```

Bactopia v3.2.0 `collect_samples` performs:

```groovy
file("${bactopia_dir}/").eachFile { item ->
    if (item.isDirectory()) {
        ...
    }
}
```

The diagnostic Batch canary showed that `isDirectory()` completed for all
preceding entries and hung specifically on `micah-test`. The isolated root
containing only `kraken-debug-0` completed.

This matches the upstream references:

- [Nextflow #6999: S3 directory path resolution hangs when prefix collides with sibling prefixes](https://github.com/nextflow-io/nextflow/issues/6999)
- [Nextflow #7224: S3ObjectSummaryLookup lists without a delimiter](https://github.com/nextflow-io/nextflow/issues/7224)
- [Nextflow PR #6851: bounded S3 lookup with `key + "/"` fallback](https://github.com/nextflow-io/nextflow/pull/6851)

## Deployed infrastructure fixes

The following changes are deployed and validated:

1. Nextflow `25.10.4` -> `26.04.6`.
2. The entrypoint derives the AWS CLI path with `command -v aws`.
3. The entrypoint writes the Nextflow work directory below an S3 prefix:

```text
s3://nextflow-spot-batch-temp-<jobid>/work
```

1. The active Batch job definition is revision `55`, using the deployed image
   digest
   `sha256:df5f867edf959b0dd31874d726a2cbe9ed531dfebed4e03d453f371119a2af80`.

The deployed actual-entrypoint smoke test used the real entrypoint, submitted a
child Batch job, and completed successfully. It verified both the dynamic AWS
CLI path and the S3 work prefix.

## AWS CLI path boundaries

The two AWS CLI path changes address different runtime boundaries:

- The kickstart entrypoint runs in the Batch parent container. It requires the
  AWS CLI to be on that container's `PATH`, discovers the path with
  `command -v aws`, and supplies it to Nextflow as `aws.batch.cliPath`. This is
  the production Batch contract validated by the deployed smoke job.
- The EC2 Bactopia test uses `/home/ec2-user/miniconda/bin/aws`, which is a
  test-host symlink to `/usr/bin/aws`. Using `/usr/bin/aws` directly caused the
  EC2 Nextflow configuration to mount the host `/usr` path into child
  containers, hiding `/usr/local/env-execute`. The Miniconda path avoided that
  mount collision and allowed child containers to start.

The EC2 symlink is not a production image requirement, and the dynamic parent
container path does not by itself prove the EC2 child mount contract. Remaining
work is to formalize the separate contracts and validate the child mount set,
including visibility of `/usr/local/env-execute`, rather than treating
`aws --version` as sufficient. No additional production entrypoint change is
currently proven necessary; the unresolved issue is the EC2-specific test
configuration and its relationship to the production child-job configuration.

## Version and runtime matrix

| Lane                        | Nextflow | Bactopia | Result                                                                                                                                         |
| --------------------------- | -------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Historical EC2/v3           | 24.04.4  | 3.2.0    | Compatible enough to run Bactopia and Kraken2; retained S3 prefix vulnerability                                                                |
| Deployed production runtime | 26.04.6  | 3.2.0    | S3 fix present, but Bactopia v3.2 config fails on `SysHelper`                                                                                  |
| EC2 candidate               | 26.04.6  | 4.1.0    | Normal Bactopia completed with QC plots disabled; post-resize no-skip QC timed out before final output; Kraken2 integration remains under test |

Bactopia v4.1.0 declares `nextflowVersion = '>=26.04.0'` in its
`nextflow.config`.

References:

- [Bactopia v4.1.0 release](https://github.com/bactopia/bactopia/releases/tag/v4.1.0)
- [Bactopia v4.1.0 `nextflow.config`](https://github.com/bactopia/bactopia/blob/v4.1.0/nextflow.config)
- [Bactopia v4.1.0 Kraken2 module](https://github.com/bactopia/bactopia/blob/v4.1.0/modules/kraken2/main.nf)
- [nf-bactopia v2.1.7 tool input implementation](https://github.com/bactopia/nf-bactopia/blob/v2.1.7/src/main/groovy/bactopia/plugin/inputs/BactopiaTools.groovy)

## Test input

The representative ONT input is from:

```text
/home/lp76/projects/cape/test-data/seqauto/caerbannog-test-sequencing-reads/sequencing
```

It contains 41 split FASTQ.GZ files. The ETL implementation confirms production
behavior: sequence members are numerically sorted and concatenated into one gzip
stream, while split files and a manifest are also preserved.

The test concatenated input has:

- 29,669 reads;
- 121,819,231 compressed bytes;
- SHA256 `1f6f3680679474e123d151ec0348bc2e33bc190b83798303ca4c3c8c47d119c4`.

Uploaded test input:

```text
s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/bactopia41-ec2-20260915143928/input/caerbannog-test.fastq.gz
```

The source metadata sample ID is `caerbannog-test`; FASTQ headers contain
`sample_id=Ecoli`. Test output names include runtime identifiers:

- `caerbannog-test-nf2404-bt320`
- `caerbannog-test-nf2604-bt410`

## Bactopia v3.2 baseline

The v3.2.0 normal Bactopia run started child containers after using the
EC2-compatible `/home/ec2-user/miniconda/bin/aws` path. It produced core QC and
assembler outputs but was marked unsuccessful because the DATASETS process
expected `v3.2.0/amrfinderplus.tar.gz` and did not see the expected output. The
direct URL returns HTTP 200, so this is a dataset/cache publication issue rather
than a missing URL.

The v3.2.0 Kraken2 baseline succeeded in 9m23s:

```text
s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/bactopia41-ec2-20260915143928/v3.2.0-kraken/bactopia/caerbannog-test-nf2404-bt320/tools/kraken2/caerbannog-test-nf2404-bt320.kraken2.report.txt
```

It found one sample, submitted and completed one Kraken2 child job, and produced
standard six-column Kraken2 output.

## Bactopia v4.1 normal run

Bactopia v4.1 normal processing completed on the resized `m5.large` EC2 launcher
with Nextflow 26.04.6 and Docker profile when `--skip_qc_plots true` was used.
DATASETS, GATHER, QC, assembler, sketcher, Prokka, AMRFinderPlus, MLST, and
merged reports completed. One assembler retry recovered.

The earlier bounded no-skip QC run was killed after approximately 85 minutes.
The post-resize no-skip validation was also bounded, completing the parent run
after 1h54m44s with the QC child still running. The QC child was AWS Batch job
`d11ca863-0b4f-479a-a565-c8d3411a4b96`; it requested 4 vCPU and 8,192 MiB, ran
for approximately 1h49m, and ended with status `FAILED`, exit code 143, and
status reason `Job killed by NF` when the parent timeout terminated it.

The QC log contains the original NanoPlot outputs but no final QC output. The
launcher remained healthy on `m5.large`, with approximately 7.1 GiB available,
no new kernel OOM evidence, and no orphaned Batch jobs after termination. This
shows that the launcher resize addressed the prior parent stability concern, but
it does not make the default QC path complete within the tested bound. The
current evidence points to a long-running QC/NanoPlot workload or insufficient
child runtime/resources, not an EC2 launcher OOM. The skip-plots resume
completed in approximately 25 minutes, which proves the rest of the v4 workflow
can complete but does not establish that the default QC path is acceptable.

A pass for the default QC path still requires final QC outputs, including the
final NanoPlot results and `main/qc/<sample>_ONT.fastq.gz`, a successful parent
and QC child, and no launcher OOM or reachability failure.

The output contract changed. Examples:

- v3 QC: `main/qc/<sample>.fastq.gz`
- v4 QC: `main/qc/<sample>_ONT.fastq.gz`
- v3 QC summaries: `main/qc/summary/*`
- v4 QC supplemental outputs: `main/qc/supplemental/*`
- v4 adds or reorganizes `main/sketcher`, `main/annotator/prokka`,
  `tools/amrfinderplus`, and `tools/mlst` outputs.

The QC modules perform broadly similar stages, but v4 uses
`bactopia-check-fastqs` instead of v3 `check-fastqs.py` and is structurally
refactored.

## Kraken2 integration findings

### V3.2.0 through Bactopia

The v3.2 tool accepts an S3 Bactopia path, finds the included sample, and
succeeds with the existing database and EC2-compatible child mount.

### V4.1.0 through Bactopia

Two separate issues were found:

1. The v4 tool input plugin does not recognize the S3 Bactopia output path in
   this setup. The plugin uses `Path.of(params.bactopia)` and reports the S3
   directory as nonexistent. Staging the completed v4 output onto shared EFS
   gets past this input step.
2. The v4 Kraken2 module ignores the ONT `lr` input slot. The v4 input plugin
   correctly identifies `main/qc/<sample>_ONT.fastq.gz` as `lr`, but
   `modules/kraken2/main.nf` derives `meta.single_end` only from `se`, `r1`, and
   `r2`. It generates `--paired null null`, producing `FileNotFoundError: null`.

The Bactopia v4.1 Kraken2 wrapper has not produced a report because of the S3
input and ONT `lr` issues. A standalone EFS-backed Kraken2 canary produced and
persisted a v4-compatible report.

### Standalone Kraken2

A standalone Nextflow process using the v4 `bactopia-teton` image, explicit ONT
input, and the shared database is the preferred way to separate Kraken2 behavior
from Bactopia's tool wrapper. The first standalone attempts found that current
analysis child hosts do not expose `/mnt/nextflow_shared_data`, even when a
host-path volume is declared. The explicit ECS-managed EFS Batch canary resolved
this: it mounted the database, processed the v4 ONT input, and produced the
persisted report documented below.

## EFS architecture finding

The workflow parent job definition has an ECS-managed EFS volume. Dynamically
created Nextflow child jobs use host-path mounts from `aws.batch.volumes`
instead. That assumes every analysis EC2 host already mounts EFS at
`/mnt/nextflow_shared_data`.

Current analysis child diagnostics show the host-path directory is absent inside
the child container. The EFS filesystem has mount targets in both required
Availability Zones, and the analysis security group is attached to the mount
targets. The likely missing piece is analysis-host EFS bootstrap or mount state,
not the EFS filesystem or security group.

The temporary EFS-backed Kraken2 canary was job
`c64f18e7-e055-42f4-8849-eb47d9c01a75`, using temporary job definition
`kraken2-efs-canary-20260916162428:1` with 16 GiB memory. It succeeded, mounted
EFS, and classified 17,563 sequences with 17,562 classified and 1 unclassified.

## Latest standalone Kraken2 findings

The persisted standalone v4 report is at:

```text
s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/batch_job_scratch/bactopia41-ec2-20260915143928/standalone-efs-canary-v4/v4-report.txt
```

The v3 and standalone v4 reports both contain 360 rows, the same taxid set, the
same classified/unclassified totals, and matching head/tail rows. They are not
byte-identical. V4 uses `D` for the Bacteria rank where v3 uses `R2`, and
low-count taxonomy rows appear in a different order. The existing DAG parser
parsed all 360 v4 rows and the HTML renderer produced a 147,823-byte report
containing the sample and Bacteria entries.

This proves that standalone Kraken2 works with the v4.1 ONT output, the Kraken2
database, the `bactopia-teton` image, and an explicit ECS-managed EFS mount. It
also shows that report integration is feasible without assuming byte-identical
output.

## Bactopia results ETL compatibility

The current results ETL is split across `assets/etl/etl_bactopia_results.py` and
`assets/etl/etl_bactopia_samples.py`. Its configured S3 contract still matches
the v4 directory structure for the files it already handles:

- v4 keeps `bactopia-runs/<run>/merged-results/amrfinderplus.tsv` and
  `merged-results/mlst.tsv`, so the result ETL's path matching and
  `pipeline-output/bactopia-runs` trigger remain valid.
- The v4 `amrfinderplus.tsv` has the expected 23 AMRFinderPlus columns. The
  existing header normalization produces the columns queried by the report,
  including `element_symbol`, `element_name`, `scope`, `type`, `method`,
  `%_coverage_of_reference`, and `%_identity_to_reference`. No AMRFinderPlus
  parser change is indicated.
- The v4 per-sample assembler and sketcher files retain the filenames matched by
  `etl_bactopia_samples.py`. The v4 assembler TSV is tab-delimited, the v4
  Sourmash result is comma-delimited as expected by its parser, and the MASH
  result is tab-delimited. These handlers do not require a v4 path change.

One required parser change was found. The v4 merged `mlst.tsv` is headered:

```text
FILE  SCHEME  ST  STATUS  SCORE  ALLELES
```

The current ETL assumes `mlst.tsv` is headerless, writes its own ten-column
header, and copies every input row. Against v4 it would therefore emit the v4
header as a data row with only six columns, followed by a six-column data row
under a ten-column header. The v4-only MLST handler should require the known
header, emit a deliberate six-column v4 schema, and represent the semicolon-
delimited `ALLELES` value as one stable field. It should fail clearly when the
header changes instead of silently producing malformed rows.

The larger compatibility gap is software metadata. The v3 Kraken2 output
published `software-versions/software_versions.yml`, which the current ETL uses
to populate `result_software_versions`. The completed v4 normal-output sample
did not publish that file. It exposed per-process `logs/versions.yml` files and
`main/gather` metadata, but neither is a replacement for the current ETL's
`Workflow` version, command, date, and `--ont` input rows. Without a stable v4
run manifest, the Bactopia report's join through `result_software_versions`
cannot populate pipeline metadata or connect the AMRFinderPlus rows by
`bactopia_run`.

The preferred compatibility fix is for the v4 submission wrapper to publish a
small `software_versions.yml` compatibility manifest with the existing
`Workflow` fields. The alternative is to change the ETL and report together to
consume a new stable v4 run-manifest schema. Per-process `versions.yml` files
are not sufficient because they do not carry the workflow command and input
mapping needed by the current report.

Bactopia v4 also publishes additional `tools/amrfinderplus`, `tools/mlst`,
`assembly-scan.tsv`, sketcher signatures, and other files. The current trigger
rules may see some of the additional TSV files, but the existing filename
matchers ignore them and exit successfully; they do not create duplicate rows.
No ingestion change is needed unless those tool-level outputs become an explicit
product requirement.

The QC rename from `main/qc/<sample>.fastq.gz` to
`main/qc/<sample>_ONT.fastq.gz` does not directly affect these results ETLs. It
affects the standalone Kraken2 input contract. Sample naming remains a separate
contract: the ETL derives `sample_id` from output filenames, so the submission
wrapper must keep the output sample name aligned with the input metadata sample
ID or provide an explicit mapping. The test runs used runtime suffixes in both
v3 and v4 sample names, so this is not a v4-only behavior.

## Explicit v4 migration plan

This is a v4-only production migration. The old v3 parser and DAG are not part
of the new runtime contract, but their versioned definitions and historical
outputs should remain available for rollback and historical access until the
cutover is accepted. The migration should not silently maintain two incompatible
output schemas.

Phase 1, select the taxonomic profiling implementation:

- Prefer an upstream-supported `nf-core/taxprofiler` path if it can satisfy the
  long-read Kraken2 requirements, AWS Batch execution, database access, report
  format, and output placement.
- Otherwise create a small standalone Kraken2 Nextflow wrapper in a new owned
  repository. Its contract should accept the v4 QC file
  `main/qc/<sample>_ONT.fastq.gz`, use the approved database/EFS or staging
  strategy, and publish `tools/kraken2/<sample>.kraken2.report.txt` with a
  stable six-column Kraken2 report.
- Do not use the Bactopia v4.1 Kraken2 wrapper as the production path unless the
  upstream S3 input and ONT `lr` defects are resolved and a production-shaped
  validation succeeds.

Phase 2, update the CAPE Cod repository:

- Replace the v3.2 pipeline profile assumptions in
  `assets/analysis-pipelines/bactopia/bactopia-base-3.2.0.json`,
  `ont-bactopia-3.2.0.json`, `kraken2-bactopia-3.2.0.json`, and their dev
  profiles with an explicit v4.1 pipeline contract. This includes pipeline IDs,
  `--ont`, `--sample`, `--outdir`, Nextflow 26.04.6, the v4 Docker profile, and
  the AWS Batch executor configuration. Bactopia v4.1 does not provide the old
  `-profile aws` contract used by the current definitions.
- Update `assets/containers/nextflow-kickstart/entrypoint.sh` only as needed to
  preserve the parent-container `command -v aws` contract. Validate that child
  jobs see the required runtime files; do not add the EC2 Miniconda symlink as a
  production image dependency.
- Update the dev and public Pulumi pipeline configuration only after the
  application contract is selected. Review Batch child resources, EFS mounting
  or database staging, work/cache prefixes, IAM, and output prefixes with
  `pulumi preview --diff`. Do not run `pulumi up` as part of this migration
  review.

Phase 3, update the external Airflow Bactopia/Kraken DAG repository:

- Identify the exact repository, owner, branch, and DAG files before editing; it
  is not checked out in this workspace.
- Replace the v3.2.0 Bactopia invocation with the v4.1 invocation and its
  supported executor/profile configuration. Update input parameters, sample
  identity, output root, cache/work prefixes, resource settings, retries, and QC
  plot policy.
- Change the QC gate from `main/qc/<sample>.fastq.gz` to
  `main/qc/<sample>_ONT.fastq.gz`.
- Replace the Bactopia v3.2 Kraken2 stage with the selected taxprofiler or
  standalone wrapper. Define the dependency on completed Bactopia QC, the
  Kraken2 database access method, the report output path, and failure/retry
  behavior.
- Preserve a versioned rollback target for the current v3 DAG without routing v4
  output through the v3.2 Kraken2 or report assumptions.

Phase 4, update results ETL and reporting in this repository:

- Change `assets/etl/etl_bactopia_results.py` to the v4 MLST header and schema.
  Validate the known header, emit the deliberate v4 `ALLELES` field, and fail
  clearly on an unexpected schema.
- Publish a v4 run metadata manifest with the fields needed by
  `result_software_versions`, or update the ETL and
  `assets/report/bactopia-single-sample-analysis/data_function.py` together to
  use a versioned replacement manifest. Preserve the `bactopia_run` join and
  input mapping required by the report.
- Keep the compatible assembler, Sourmash, MASH, and AMRFinderPlus handlers
  unless the product contract expands. Confirm Glue triggers, crawler table
  names, partition columns, and the report's Athena joins against a complete v4
  output tree.

Phase 5, validate the complete path before cutover:

1. Reconcile the completed post-resize no-skip QC validation. The parent and
   child IDs, child resources, exit reason, final QC state, launcher health, and
   orphan cleanup status are now recorded above. Decide whether the production
   policy is a higher QC child allocation, a longer runtime bound, or an
   intentional plot-skip policy.
2. Run the selected Kraken2 implementation with a production-shaped EFS or
   staging configuration, not only the explicit canary job definition.
3. Run v4 outputs through the ETL in a dev environment and verify MLST,
   AMRFinderPlus, software metadata, crawler partitions, report joins, and HTML
   rendering.
4. Run the updated Airflow DAG in dev with an isolated S3 prefix and compare
   semantic contracts: sample identity, QC path, report path, report totals,
   output completeness, and failure behavior.
5. Review `pulumi preview --diff` for the target stack. Every resource action
   must map to an approved change before the user deploys.

Phase 6, cut over and restore test resources:

- Deploy the selected CAPE and Airflow changes only after the dev gates pass and
  the owner approves the preview.
- Keep v3 definitions and historical output readable for rollback, but use the
  v4-only ETL and DAG contract for new production runs.
- Restore `i-01274bddc155993e8` from `m5.large` to its original `t3.micro` after
  validation, remove the test-only Miniconda AWS symlink if no further tests
  require it, and leave scratch EFS/S3 data untouched until separately approved
  for cleanup.

## Current next actions

1. Run the representative Bactopia v4.1 -> taxprofiler Kraken2 -> ETL -> report path in an isolated dev environment.
2. Define and publish the v4 crawlable run-metadata sidecar with the fields required by `result_software_versions`, `bactopia_run`, and report joins.
3. Validate Glue triggers, crawler partitions, Athena queries, report rendering, and semantic Kraken2 output behavior against the v4 contract.
4. Keep the external Airflow DAG update as a separate repository handoff.
5. Prepare the final Issue 379 cutover and rollback evidence after the representative path succeeds.

The temporary Kraken2 job definitions were deregistered. The durable
representative report evidence remains in the recorded canary outputs; temporary
normal-DAP output was deleted after verification.
