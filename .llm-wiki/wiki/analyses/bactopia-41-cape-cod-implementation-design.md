---
type: analysis
title: Bactopia 4.1 CAPE Cod implementation design
created: 2026-09-16
updated: 2026-09-23
status: current-design-reference
---

# Bactopia 4.1 CAPE Cod implementation design

Status: design baseline, revised after owner feedback and dev validation. This document describes
the CAPE Cod changes needed to support Bactopia v4.1 and a separate long-read
taxonomic profiling stage. It is intended to guide implementation by an engineer
or LLM. It is not a deployment approval and does not define the complete
frontend or external Airflow DAG design.

Implementation scope is this `cape-cod` repository only. CAPE Cod owns the MWAA
environment deployment and configuration needed by this migration. External
Airflow DAG source, frontend work, and any new profiler-repository work are
recorded as interface and handoff requirements, but must not be edited from this
task unless the owner explicitly expands scope. The DAG and frontend work are
expected to be owned by other implementers.

Current status as of 2026-09-23: the Bactopia v4.1 profiles, v4 ETL contract
adapters, standalone `nf-core/taxprofiler` Kraken2 route, runtime export, and
Decimal-safe DAP submission are implemented and deployed. The remaining
migration gate is a representative Bactopia -> taxprofiler -> ETL -> report
run plus the v4 crawlable run-metadata sidecar. The EFS bridge and generic
capability design remain separate follow-on material for PR 385 and issues
381/380.

Related evidence and handoff:

- [[analyses/kraken2-and-bactopia-41-migration-findings]]
- [[analyses/bactopia-41-new-session-handoff]]
- [[analyses/bactopia-41-ec2-validation-handoff]]

## 1. Scope and outcome

The target is a v4-only contract for new Bactopia runs. The current v3.2
pipeline definitions and historical output remain available for rollback and
historical access, but new v4 outputs must not be routed through v3.2-only
Kraken2, QC, ETL, or report assumptions.

The implementation must provide:

1. A CAPE Data Analysis Pipeline profile for Bactopia v4.1 ONT processing.
2. A supported way to run the workflow under AWS Batch after Bactopia v4.1
   removed the v3.2 `-profile aws` behavior used by the current fixtures.
3. A selected long-read taxonomic profiling implementation. The selected
   implementation is `nf-core/taxprofiler` v2.0.1. The first CAPE route is a
   Kraken2-only preset, while native outputs must remain available for future
   taxonomic tools.
4. A stable output contract for Bactopia v4, the profiler, Glue ETL, crawlers,
   report queries, and HTML rendering.
5. A dev-only validation path and an explicit Pulumi preview/deployment gate.
6. Clear external-repository interface and handoff requirements for the Airflow
   Bactopia/Kraken DAG and any new profiler repository. These are not
   implementation tasks in this repository unless the owner expands scope.

This document does not design frontend changes or the full external DAG. It
specifies the interfaces those systems must consume, the CAPE-owned MWAA
configuration/deployment changes, and the work another owner must perform.

### 1.1 Current branch boundary and follow-on architecture

The current branch must make Bactopia v4.1 and the selected taxprofiler Kraken2
route work without turning this migration into a general Batch scheduler
redesign. The current terminology for a future logical execution contract is:

- `taxonomic-profiling` - an execution class for Kraken2, Bracken, MetaPhlAn,
  and related taxonomic tools.
- `taxonomic-reference-data` - a logical resource or volume reference. It is
  not a Kraken2-specific name and does not contain a physical EFS identifier.

A tactical host-mounted EFS bridge may be used for the current migration if it
can be made reliable. The generic execution-class, capability-aware placement,
zero-to-many volume dependency, and changing-resource-ID model are a separate
follow-on. The local follow-on design is recorded in
`.llm-wiki/wiki/analyses/cape-pipeline-execution-classes-and-resource-capabilities.md`.

The user-facing Batch documentation draft remains a temporary decision aid. It
must not be treated as a committed product document until the host/child
runtime and database-access contracts are settled.

## 2. Validated constraints and decisions

### 2.1 Runtime

- Bactopia v3.2.0 cannot parse under Nextflow 26.04.6 because its config imports
  `nextflow.util.SysHelper`.
- Bactopia v4.1.0 requires Nextflow `>=26.04.0`.
- The deployed kickstart image uses Nextflow 26.04.6 and nf-amazon 3.9.2.
- The deployed Batch runtime currently uses the validated Nextflow 26.04.6 image
  and job-definition configuration. Image digests, job-definition revisions,
  queues, subnets, security groups, EFS IDs, and other AWS resource IDs are
  deployment outputs and must not be hard-coded in pipeline profiles or source
  code.
- The original S3 prefix-collision hang is fixed by the deployed runtime.

### 2.2 AWS CLI path boundaries

There are two separate path contracts and they must not be conflated.

The production kickstart parent container must have the AWS CLI on `PATH` for
parent operations such as creating temporary work buckets. The entrypoint may
continue to derive the parent path with `AWS_CLI_PATH=$(command -v aws)`, but
that value must not automatically become the child host's `aws.batch.cliPath`.

Nextflow interprets `aws.batch.cliPath` as the path to the AWS CLI on the Batch
host AMI. It mounts the grandparent directory of that path into child
containers. The current deployed `awsbatch` AMI, built from
<https://github.com/cape-ph/aws-batch-ecs-ami>, provides the safe host path:

```text
/home/ec2-user/miniconda/bin/aws
```

Using the parent container path `/usr/bin/aws` as the child host path mounts the
host `/usr` directory into child containers and can hide `/usr/local` files such
as `/usr/local/env-execute` and Wave image entrypoints. The parent container
path and the child host AMI path are separate runtime contracts.

The generated runtime must resolve both values from their correct boundaries.
It must validate child-container mounts and visibility of
`/usr/local/env-execute`; `aws --version` alone is not an adequate test. The
host CLI directory must be installed on every relevant Batch AMI or bootstrap
path, not only on one currently running instance.

### 2.3 QC policy

The v4 workflow completed with `--skip_qc_plots true` in approximately 25
minutes. A post-resize no-skip run requested 4 vCPU and 8,192 MiB for the QC
child and was still running after approximately 1h49m when the bounded parent
run terminated it. It produced original NanoPlot artifacts but no final QC
output. The launcher remained healthy on `m5.large` and had no new OOM evidence.

The initial production policy should skip QC plots. The v4 DAP profile must
expose `--skip_qc_plots` as a configurable boolean with a default of `true`, so
an external caller or future frontend control can request the full QC path by
setting it to `false`. Frontend behavior is outside this repository's scope.

The profile, runtime documentation, and acceptance tests must state that the
normal v4 path skips plots. A separate opt-in test must cover the no-skip path
before treating it as supported. The existing `--skip_qc_plots` result proves
that the non-plot workflow completes; the default no-skip path remains a known
long-running option.

### 2.4 Kraken2

The Bactopia v4.1 Kraken2 wrapper is not usable as-is for the current ONT/S3
workflow. The v4 input plugin did not resolve the S3 Bactopia path in this
setup, and the v4 Kraken2 module ignored ONT input in the `lr` slot and
generated `--paired null null`.

A standalone EFS-backed Kraken2 canary succeeded against the v4 ONT QC output.
The resulting report had the same 360-row taxid set and classification totals as
v3, but differed in rank code and low-count ordering. The existing report parser
and HTML renderer handled the v4 report.

The profiler decision is complete: use `nf-core/taxprofiler` v2.0.1. The
first route should enable Kraken2 only, preserve the native taxprofiler output
tree for future tools, and produce a CAPE-normalized Kraken2 compatibility
report at the stable report path. The Bactopia v4 Kraken2 wrapper remains out
of scope unless its upstream issues are independently resolved.

### 2.5 Database access

The Kraken2 database is approximately 7.5 GiB. The explicit canary succeeded
with an ECS-managed EFS mount. Normal Nextflow child jobs currently use a
host-path mount such as:

```text
/mnt/nextflow_shared_data:/mnt/nextflow_shared_data:ro
```

The design must select one supported production strategy:

1. Mount EFS on every analysis host at `/mnt/nextflow_shared_data` and keep the
   existing host-path Nextflow contract.
2. Stage the database from S3 into each child job's local storage, with explicit
   performance, storage, and cost limits.
3. Build a supported child-job path that can attach ECS-managed EFS directly.
   This is not supplied by the current Nextflow `aws.batch.volumes` host-path
   configuration and should not be assumed to work without an implementation.

The first option is the closest to the successful canary, but it requires an
analysis-host bootstrap/AMI change. The second option may be preferred if the
workflow platform cannot guarantee EFS mounts. The decision belongs in the
profiler workstream and must be validated with a production-shaped child job.

All resource identifiers must be resolved from deployment outputs, runtime
configuration, or a platform registry. The implementation must not place an EFS
filesystem ID, job-definition ARN, queue ARN, subnet ID, security-group ID, or
image digest in a DAP fixture. If a run needs a durable association that cannot
be resolved programmatically, first design a versioned internal registry record,
such as a DynamoDB row keyed by the CAPE run ID. That registry option is an
iterative design item, not an assumption for this phase.

## 3. Current CAPE Cod architecture

### 3.1 DAP profile fixtures

The current Bactopia fixtures are:

- `assets/analysis-pipelines/bactopia/bactopia-base-3.2.0.json`
- `assets/analysis-pipelines/bactopia/bactopia-base-dev.json`
- `assets/analysis-pipelines/bactopia/ont-bactopia-3.2.0.json`
- `assets/analysis-pipelines/bactopia/ont-bactopia-dev.json`
- `assets/analysis-pipelines/bactopia/kraken2-bactopia-3.2.0.json`
- `assets/analysis-pipelines/bactopia/kraken2-bactopia-dev.json`

The base fixtures currently expose `-profile aws` and `--aws_volumes`. The v4
workflow does not define the old `aws` profile. The current Kraken2 fixtures
also expose `--wf kraken2`, `--kraken2_db`, and `--bactopia`, which are tied to
the v3.2 Bactopia wrapper and should not be carried into a v4 profiler profile
without validation.

### 3.2 Kickstart runtime

`assets/containers/nextflow-kickstart/Dockerfile` installs Nextflow 26.04.6,
Java 21, Git, Python, curl, jq, and the AWS CLI. It should not be changed only
to encode the EC2 Miniconda path.

`assets/containers/nextflow-kickstart/entrypoint.sh` currently:

- obtains the AWS region from ECS metadata when needed;
- stages a pipeline into `/scratch`;
- creates a temporary S3 work bucket;
- discovers the AWS CLI path with `command -v aws`;
- generates `/nextflow.config` with the AWS Batch executor, queue, region, and
  `aws.batch.cliPath`;
- sets `BACTOPIA_CACHEDIR` to an S3 scratch prefix; and
- runs Nextflow with the generated config and S3 work directory.

The v4 design should keep the generated parent config instead of recreating a
Bactopia v3 `-profile aws`. The preferred first implementation is one shared
CAPE-wide Nextflow runtime config for all Nextflow DAPs. It should own the
execution concerns common to wrapped pipelines:

- `process.executor = 'awsbatch'`;
- dynamic queue and region resolution;
- dynamic `aws.batch.cliPath` resolution;
- common work/cache behavior; and
- the selected common database/staging contract when it applies across the
  platform.

The shared config must resolve runtime values from environment, deployment
outputs, or platform context. It must not contain hard-coded AWS resource IDs or
host-specific paths. Pipeline profiles should contain pipeline source, revision,
profile flags, user parameters, and output contracts, not a second copy of the
AWS Batch execution config.

The current generated config contains a Kraken-specific `withName` selector for
symlink staging. That is a known exception to the shared-config goal. The first
implementation should test whether it can be removed or expressed as a generic
capability. If a pipeline-specific override is required, add the smallest
explicit opt-in fragment and record owner approval for the deviation.

This is a configuration design iteration, not a final schema mandate. The DAP
registry has a loose conceptual place for Nextflow configuration, but no usable
config contract was found in this checkout. Inspect that model before adding
fields. A candidate profile reference is:

```json
{
    "nextflow": {
        "runtime_config": "cape-nextflow-batch-v1",
        "pipeline_config": "bactopia-4.1"
    }
}
```

The names above are conceptual. The normal path should render one shared
`/nextflow.config` for the run. `pipeline_config` should be metadata and
validated pipeline options, not an instruction to create a second runtime
config. User-supplied arbitrary config text should not be accepted initially.

The shared-config-first merge order should be explicit and tested: shared
platform runtime config, any owner-approved pipeline override, then validated
pipeline parameters. The platform assumes one supported Nextflow version for
now. The shared config and each pipeline profile should document where a future
Nextflow version could change behavior, so a later runtime matrix can be added
without hiding compatibility assumptions.

## 4. Target architecture

The target flow is:

```text
input-clean sequencing reads
  -> external Airflow Bactopia v4 DAG
  -> CAPE DAP profile and kickstart parent
  -> Bactopia v4.1 ONT workflow on AWS Batch
  -> v4 QC output: main/qc/<sample>_ONT.fastq.gz
  -> selected profiler on AWS Batch
  -> tools/kraken2/<sample>.kraken2.report.txt
  -> result-raw pipeline-output/bactopia-runs/<run>/...
  -> Glue ETL and result-clean crawler tables
  -> single-sample report queries and HTML renderer
```

The user-facing report path is deliberately kept stable for Kraken2 so the
existing report parser can be reused initially. The implementation must still
validate report semantics rather than relying on byte equality.

## 5. CAPE Cod changes

### 5.1 Add v4 pipeline profile fixtures

Add versioned v4 fixtures rather than mutating the v3 fixtures in place:

- `assets/analysis-pipelines/bactopia/bactopia-base-4.1.0.json`
- `assets/analysis-pipelines/bactopia/ont-bactopia-4.1.0.json`
- `assets/analysis-pipelines/bactopia/taxprofiler-kraken2-2.0.1.json`, the
  initial Kraken2-only taxprofiler preset.

The v4 base fixture should:

- identify the Bactopia v4.1.0 Nextflow project and version;
- set `-profile docker`, not `-profile aws`;
- omit the v3-only `--aws_volumes` user parameter;
- preserve the `nextflowOptions` CLI-string submission interface;
- expose only parameters the selected v4 workflow actually accepts; and
- document that AWS Batch executor settings come from the kickstart-generated
  config rather than from a Bactopia `aws` profile.

The v4 ONT fixture should retain the stable user inputs `--ont`, `--sample`, and
`--outdir`, with v4 descriptions and defaults. It should document the canonical
output root and the QC path used by downstream stages.

Do not delete the v3 fixture files in the initial migration. They are the
versioned rollback and historical reference. Deletion, if still desired, is a
separate post-cutover cleanup decision.

### 5.2 Replace the lost `-profile aws` behavior

The v3 profile bundled executor and volume behavior through Bactopia's `aws`
profile. V4 requires the equivalent behavior from the CAPE runtime layer.

The implementation should:

1. Make the generated `/nextflow.config` the single shared execution config for
   Bactopia, the selected profiler, and future Nextflow DAPs.
2. Keep `process.executor`, Batch queue, region, work/cache behavior, and
   parent-container `aws.batch.cliPath` in that shared config.
3. Pass Bactopia v4 `-profile docker` and pipeline-specific options through the
   DAP profile without recreating AWS Batch settings.
4. Avoid exposing a raw EC2 host path as a user-facing `--aws_volumes` value.
5. Attempt to express the selected database mount/staging behavior in the shared
   config. Deviate with a pipeline override only when the shared config cannot
   support the behavior, and require owner approval for that deviation.
6. Add a runtime test that submits different wrapped pipelines and verifies the
   shared config, child mount set, and expected runtime files.

The current EC2-only `/tmp/nextflow-aws-ec2-v4.config` is test scaffolding, not
a production artifact. If an equivalent static config is required for local test
or dev execution, add it under a clearly named test/config directory. The first
production implementation should attempt the shared generated config before
adding static per-pipeline config files.

### 5.3 Update the kickstart image only when required

The expected initial change is no Dockerfile change. Retain the deployed
Nextflow 26.04.6 image and dynamic AWS CLI discovery.

If tests demonstrate a real production gap, modify
`assets/containers/nextflow-kickstart/entrypoint.sh` in a separate commit to:

- resolve the AWS CLI path before the first AWS CLI invocation;
- fail with a clear message when the CLI is absent;
- preserve generated S3 work/cache behavior; and
- add no host-specific `/home/ec2-user` path.

Any image change requires a dev `pulumi preview --diff`, a Batch smoke test, and
owner-approved deployment. The EC2 symlink must never be added to the image.

## 6. Kraken2 or taxprofiler integration

### 6.1 Selected profiler validation gate

The profiler decision is complete: use `nf-core/taxprofiler` v2.0.1. The
initial CAPE route enables Kraken2 only, while the integration must preserve the
native taxprofiler output tree for future tool presets.

The remaining validation gate covers:

- ONT long-read input support;
- Kraken2 database and location semantics;
- AWS Batch executor and host CLI behavior;
- the selected EFS host-mount bridge or another approved database strategy;
- process-specific resource overrides;
- native output shape and canonical compatibility report placement; and
- operational logs, retries, and failure behavior.

The initial S3 sheet, host CLI, child staging, and resource probes are recorded
in the migration findings. The next production-shaped test must use the real
EFS-backed database and must not silently fall back to S3 staging.

### 6.2 Standalone wrapper contract

If a wrapper is selected, the new repository must provide:

- a pinned Nextflow workflow release or commit;
- a small input channel accepting a sample ID and one ONT FASTQ.GZ;
- an explicit Kraken2 database parameter;
- a container image with the required Kraken2 version;
- AWS Batch execution configuration compatible with the CAPE kickstart;
- EFS or S3 database staging behavior with documented storage requirements;
- the canonical report path `tools/kraken2/<sample>.kraken2.report.txt`; and
- tests for report row shape, classified totals, taxid set, and parser/rendering
  compatibility.

The wrapper should not depend on Bactopia's internal input plugin or on the v4
`lr` slot. It should read the published v4 QC file directly.

### 6.3 CAPE profiler fixture

Add one versioned taxprofiler profile under
`assets/analysis-pipelines/bactopia/`. It should replace the current
`kraken2-bactopia-3.2.0.json` user interface for new v4 runs, but should not
silently invoke the Bactopia v4 Kraken2 wrapper. The first preset should be a
Kraken2-only route while preserving a generic taxprofiler boundary for future
tool selections.

The fixture should expose only stable parameters such as:

- sample ID;
- v4 Bactopia output location or direct QC FASTQ location;
- output location;
- database reference or approved database selector;
- CPU and memory limits; and
- any profiler-specific required options.

Do not expose a parameter whose meaning depends on an unvalidated host mount.

### 6.4 Database and EFS infrastructure

The selected strategy determines infrastructure changes:

Host-mounted EFS strategy:

- update the analysis compute host AMI/bootstrap path so every relevant child
  host mounts the EFS resource resolved from the deployment/runtime
  configuration at `/mnt/nextflow_shared_data`; do not hard-code the filesystem
  ID;
- preserve the existing read-only container mount;
- confirm mount targets, security group rules, and IAM/network behavior;
- validate a real profiler child on each required Availability Zone; and
- update the Nextflow config only after the host path is guaranteed.

S3 staging strategy:

- stage the database into child local storage before classification;
- define minimum ephemeral storage and memory;
- define cache reuse behavior and expected startup time;
- grant only the required S3 read permissions; and
- keep the output/report path independent of staging paths.

Direct ECS-managed EFS child strategy:

- treat this as a separate platform implementation, not as a consequence of
  setting `aws.batch.volumes`;
- define how a child job receives `efsVolumeConfiguration`; and
- prove that Nextflow can submit that job shape before choosing it.

The explicit EFS canary proved the database and container behavior. It did not
prove that normal Nextflow-created child jobs receive managed EFS.

## 7. Bactopia v4 output and metadata contract

### 7.1 QC and sample output

The v4 QC input for the profiler is:

```text
<outdir>/<sample>/main/qc/<sample>_ONT.fastq.gz
```

V4 supplemental QC metadata is under `main/qc/supplemental/`. V4 also adds or
reorganizes sketcher, Prokka, AMRFinderPlus, and MLST outputs. The external DAG
must use the v4 QC filename and must not search for the v3 QC filename.

Sample identity must be explicit. The ETL derives sample IDs from output
filenames, while test runs used runtime-distinguishing suffixes. The external
DAG must ensure that the output sample name, input metadata sample ID, report
sample ID, and result table partition use the intended canonical identity.

### 7.2 Run manifest

V4 normal output did not publish the v3-style
`software-versions/software_versions.yml`. The report currently depends on that
table for Bactopia version, run date, input mapping, and the `bactopia_run` join
used for AMRFinderPlus.

The current report does not read the software-version YAML directly. The ETL
reads result objects, writes CSV to result-clean, Glue crawls the CSV, and
`assets/report/bactopia-single-sample-analysis/data_function.py` reads the
catalog through Athena. Therefore a YAML file inside the Bactopia output is not
required solely for report rendering.

The preferred design is a CAPE-owned run metadata sidecar outside the tool's
published result tree:

```text
pipeline-output/cape-metadata/bactopia-runs/<run>/run-manifest.json
```

The sidecar should be written by the orchestration layer that knows the CAPE run
ID, not by a modified Bactopia repository. It should contain a versioned schema
with sample ID, Bactopia version, supported Nextflow runtime, run date, input
object, output root, QC path, output-contract version, and selected profiler.
The exact writer is an external orchestration dependency and is not implemented
in this repository under the current scope.

In CAPE Cod, add a dedicated metadata ETL such as
`assets/etl/etl_bactopia_run_metadata.py` or an equivalent adapter in the
existing Bactopia ETL. It should write a crawlable metadata table keyed by
`bactopia_run`. The result ETL should derive the run ID from the actual result
key and join to the metadata table through Athena. The report should query that
CAPE-owned table for pipeline metadata and retain the AMRFinderPlus join through
`bactopia_run`.

This avoids adding an uncontrolled file to Bactopia output. If the orchestration
layer cannot reliably publish the sidecar, evaluate a DynamoDB run registry or a
compatibility manifest as a separate design iteration. A registry must still
produce a stable, crawlable/reportable association and must not hard-code AWS
resource IDs in source code. Per-process `logs/versions.yml` files remain
insufficient because they do not carry the workflow command and CAPE input
mapping needed by the report.

## 8. ETL and report changes in this repository

### 8.1 `assets/etl/etl_bactopia_results.py`

Change the script from a mixed historical filename handler to a version-agnostic
ETL core with explicit output-contract adapters. The active adapter for the v4
cutover should be selected by a declared output-contract schema or manifest, not
by a brittle exact Bactopia version comparison.

Required changes:

- Introduce an adapter interface with responsibilities for matching files,
  validating headers, parsing MLST/AMRFinderPlus, reading run metadata, and
  constructing output keys.
- Implement the initial v4-compatible adapter against the observed headered MLST
  and AMRFinderPlus files. Name it for the output contract, such as
  `BactopiaOutputContractV1Adapter`, not `BactopiaV41Adapter`.
- Allow the same adapter to support later Bactopia 4.x releases when their
  output contract is unchanged. Add a new adapter only when a schema or semantic
  change requires one.
- Keep matching `merged-results/amrfinderplus.tsv` and validate its report-query
  columns.
- Require the v4 MLST header: `FILE`, `SCHEME`, `ST`, `STATUS`, `SCORE`,
  `ALLELES`.
- Emit a stable six-column MLST CSV schema and preserve `ALLELES` as one
  semicolon-delimited field unless the product requirement calls for gene-level
  columns.
- Reject or log a clear schema error when the selected contract changes.
- Read the CAPE-owned run metadata table or sidecar adapter rather than assuming
  a Bactopia-owned software-version file.
- Keep adapter selection and output schemas independently versioned from the
  Bactopia release string. Document which Bactopia releases use each adapter.

For the initial implementation, keep the adapter classes and helpers in the ETL
files that use them, especially `etl_bactopia_results.py` and
`etl_bactopia_samples.py`. Do not add a shared adapter module only for
architectural purity. Extract adapters later when reuse or complexity justifies
it, with explicit Glue packaging and import tests. Do not introduce a class name
that requires users to know which Bactopia release happens to reuse a contract.

The output partition remains:

```text
<result-table>/bactopia_run=<run-id>/<object-name>.csv
```

The `bactopia_run` value must match across software metadata and AMRFinderPlus.

### 8.2 `assets/etl/etl_bactopia_samples.py`

The v4 assembler and sketcher filenames remain compatible with the current
handlers. The initial v4 implementation should:

- retain the assembler, Sourmash, and MASH table names;
- validate v4 delimiters and headers with fixtures;
- ensure the canonical sample ID is used for the output partition; and
- ignore new v4 tool files unless a product requirement adds them.

Refactor the filename matcher into a small table of named v4 handlers rather
than adding more greedy regular expressions. This creates a clear extension
point for future output versions without maintaining the old v3 behavior.

The new v4-only implementation does not need to ingest duplicate
`tools/amrfinderplus` or `tools/mlst` files because the merged results are the
canonical inputs for the current tables.

### 8.3 Pulumi and Glue configuration

Review `Pulumi.cape-cod-dev.yaml`. The public Pulumi configuration is generated
from the dev configuration by CI/CD and must not be edited directly. The current
seqauto data pipeline registers:

- `etl_bactopia_results.py` on `pipeline-output/bactopia-runs` with TSV/YML
  suffixes; and
- `etl_bactopia_samples.py` on `pipeline-output` with TSV/TXT suffixes.

The v4 implementation should preserve these triggers if the output keys remain
unchanged. Update them only when the v4 run manifest or new profiler output
prefix requires a new trigger. Check that:

- the script asset registration points to the new code;
- the Glue job has `pyyaml` and any new dependency;
- the crawler still produces the intended `result_*` tables;
- MLST and software metadata schemas are stable across partitions; and
- the new profiler report does not accidentally trigger a Bactopia ETL.

If the chosen profiler writes a new top-level result table, add a dedicated
ETL/crawler contract rather than overloading the Bactopia result handler.

### 8.4 `assets/report/bactopia-single-sample-analysis/data_function.py`

Keep the existing report table names where possible:

- `result_software_versions` for pipeline metadata;
- `result_sourmash_gtdb_rs207_k31` for organism information; and
- `result_amrfinderplus` joined through `bactopia_run`.

If the v4 manifest preserves the existing table contract, the report query only
needs validation and a v4 fixture. If the manifest schema changes, update the
metadata query, AMRFinderPlus join, date parsing, and version rendering in the
same change. Do not partially migrate the ETL and leave the report expecting a
missing table.

The existing Kraken2 parser/renderer can be reused initially. Its acceptance
checks must compare semantic rows, taxid sets, classification totals, key taxa,
and rendered sample/Bacteria entries. Do not require byte-identical rank codes
or row order.

## 9. External dependency handoff, not implementation scope

The following work belongs to other implementers or repositories. This CAPE Cod
task must not edit those repositories unless the owner explicitly expands scope.
The exact repository, owner, branch, and file paths must be identified before
handoff.

### 9.1 Airflow Bactopia/Kraken DAG repository

The full DAG design is intentionally out of scope here, but the DAG must change
these interfaces:

- Bactopia revision from v3.2.0 to v4.1.0.
- Nextflow runtime to 26.04.6 or the supported CAPE runtime.
- Bactopia profile from the v3 `aws` assumption to the v4 Docker plus generated
  Batch config contract.
- Input parameter, sample identity, output root, cache/work prefixes, and
  resource settings.
- QC gate from `<sample>.fastq.gz` to `<sample>_ONT.fastq.gz`.
- Default QC plot policy and timeout/retry behavior.
- Bactopia run-manifest publication.
- Kraken2 stage replaced by the selected profiler, with database access,
  dependency on completed QC, canonical report path, and retry behavior.
- Output publication under the result-raw prefix watched by the v4 ETL.

Preserve a versioned v3 DAG target for rollback. Do not route v4 output through
v3.2 Kraken2 or v3 report assumptions.

### 9.2 New standalone profiler repository, if required

Create a new repository only if `nf-core/taxprofiler` fails the decision gate.
The repository should own the workflow, tests, container pin, output contract,
AWS Batch configuration, and database staging behavior. CAPE Cod should consume
it through a versioned DAP fixture rather than embedding its source into this
repository.

The new repository must publish its own run metadata and versions so ETL does
not need to infer profiler behavior from arbitrary process logs. The CAPE result
contract should remain stable if the profiler implementation changes later.

### 9.3 CAPE-owned MWAA deployment and configuration

CAPE Cod owns the MWAA environment and its infrastructure/configuration. Review
`Pulumi.cape-cod-dev.yaml` for the MWAA environment, Airflow version/config, DAG
path, execution role, Batch pass-role permissions, and any variables or
connections needed by the v4 workflow. Do not edit
`Pulumi.cape-cod-public.yaml`; CI/CD generates it from dev configuration.

The external DAG repository and its source files remain outside this task. The
external `cape-cod-env` or equivalent deployment path may own DAG
synchronization and DAG-level variables, so the handoff must define that
boundary. CAPE Cod changes should establish the MWAA infrastructure contract
without editing the DAG source.

## 10. Demo compatibility and platform generalization gates

The Aiken demo branch review identified adjacent changes that were necessary for
that demo but are not automatically durable platform behavior. The migration
must either resolve these items during the Bactopia v4 effort or track and
complete them immediately afterward before the migration is considered
successful. See [[analyses/aiken-demo-platform-generalization-review]].

### 10.1 Frontend image selection

The demo changed the dev `cape-frontend` AMI selection. This must not become an
implicit Bactopia or platform dependency. The external frontend owner should
replace demo-specific image selection with the maintained frontend image/release
process. CAPE Cod should keep the dev configuration free of unexplained demo AMI
pins and should record the accepted image source in the normal platform process.
This is an external implementation handoff, but it is a migration success gate.

### 10.2 Reports API contract

The demo changed `reports/get` from returning report HTML strings to returning
objects with `createdAt` and `body`. Before this is treated as a durable
platform contract, CAPE Cod must have an API contract test and the owning
frontend must migrate to the new shape. If the metadata is not a platform
requirement, the response change must be isolated or reverted rather than left
as demo-only API drift.

### 10.3 Caerbannog/RABiTS reporting architecture

The demo changed the Caerbannog/RABiTS report presentation and duplicated the
Bactopia report template inside the ETL. The durable data normalization and
partition contract must be separated from the temporary HTML rendering. Before
migration success, the team must either move rendering into an accepted
reporting component or explicitly accept and document the temporary behavior
with a follow-up owner and issue. This is adjacent to the Bactopia migration but
should not become a general Glue ETL pattern.

These gates may be implemented by different owners. CAPE Cod must record the
interface, test, issue, and ownership status before declaring the migration
complete.

## 11. Tests and acceptance gates

### 10.1 Profile and config tests

Add tests or validation fixtures that verify:

- v4 profile inheritance resolves correctly;
- the schema emits `-profile docker`, not `-profile aws`;
- v3-only `--aws_volumes` is absent from the v4 user contract;
- required `--ont`, `--sample`, and `--outdir` values are present;
- the generated Batch config includes queue, region, executor, and CLI path;
- a child container sees its intended mounts and `/usr/local/env-execute`; and
- no production profile contains the EC2 Miniconda path.

### 10.2 Bactopia v4 integration test

Run the representative ONT input in an isolated S3 root. Record:

- Nextflow/Bactopia versions;
- parent and child Batch IDs;
- queue, job definitions, requested and actual resources;
- QC policy and runtime;
- output tree completeness;
- v4 QC path and run manifest;
- merged AMRFinderPlus and MLST outputs; and
- no orphaned jobs after completion or timeout.

The test must not use the production `pipeline-output` prefix and must not clean
scratch data without approval.

### 10.3 Profiler test

The selected profiler must:

- read the v4 `_ONT.fastq.gz` file;
- access its database through the selected EFS/staging path;
- complete in a production-shaped child job;
- publish the canonical report path;
- produce the expected six-column report;
- pass semantic comparison against the standalone v4 baseline; and
- pass the existing parser and HTML renderer.

### 10.4 ETL/report test

Use checked-in v4 fixtures for:

- headered MLST;
- AMRFinderPlus;
- software manifest;
- assembler, Sourmash, and MASH outputs; and
- canonical sample/run IDs.

Verify output CSV headers, partitions, Glue crawler table names, Athena joins,
pipeline metadata, AMRFinderPlus rows, organism rows, and HTML output. Use
`python -m py_compile` only as a syntax check, not as migration acceptance.

### 10.5 Infrastructure gate

Run:

```text
pulumi preview --diff -s <target-stack>
```

Reconcile every create, update, replace, or delete with the approved migration.
The owner performs any deploy. Never run `pulumi up` as part of this design or
implementation without explicit approval.

## 12. Proposed phased commits

These are implementation commit boundaries, not commits to create now.
Cross-repository changes should use equivalent phases in their own repositories.

### Commit 1: document the contract

`docs(bactopia): define v4.1 migration contract`

- Add or update the findings, handoff, and design documents.
- Record open choices and acceptance gates.
- Add no runtime behavior.

### Commit 2: add v4 CAPE profiles

`feat(pipelines): add Bactopia v4.1 profiles`

- Add `bactopia-base-4.1.0.json`.
- Add `ont-bactopia-4.1.0.json`.
- Add tests/fixtures for profile inheritance and parameter schema.
- Do not delete v3 fixtures.

### Commit 3: make Batch runtime configuration explicit

`fix(runtime): support Bactopia v4 Batch configuration`

- Modify the kickstart entrypoint only if the generated config needs a verified
  change.
- Add tests for dynamic CLI discovery and child runtime mounts.
- Add or update the selected EFS/host bootstrap infrastructure only after
  approval and preview.

### Commit 4: implement v4 ETL contracts

`fix(etl): ingest Bactopia v4 results`

- Update `etl_bactopia_results.py` for v4 MLST and run manifest.
- Refactor `etl_bactopia_samples.py` handlers for explicit v4 outputs.
- Add v4 fixtures and unit tests.
- Update the dev Glue registration only if required. CI/CD generates the public
  configuration from dev; do not edit the public Pulumi file directly.

### Commit 5: add the selected profiler integration

`feat(pipelines): add v4 taxonomic profiling pipeline`

- Add the pinned `nf-core/taxprofiler` v2.0.1 DAP fixture.
- Configure the Kraken2-only preset while keeping the broader taxprofiler
  output contract available for future tools.
- Add canonical report-path and semantic parser tests.
- Record the selected host-mounted EFS bridge and its runtime resource policy.

### Commit 6: validate reports and dev integration

`test(bactopia): validate v4 ETL and report integration`

- Run the isolated v4 output through Glue/ETL/crawler/report validation.
- Validate sample identity, metadata joins, AMRFinderPlus, MLST, and profiler
  report rendering.
- Record the dev result and any required follow-up.

### Commit 7: hand off external orchestration changes

The external Airflow/DAG implementer should update the Bactopia DAG, profiler
stage, resource policy, run metadata sidecar, output paths, and deployment
configuration only after CAPE Cod dev validation passes. This repository should
record the interface and acceptance result; it should not modify the external
repository under the current scope. Production deployment remains an owner
operation after preview review.

### Commit 8: post-cutover cleanup

`chore(bactopia): retire temporary v4 migration resources`

Only after rollback retention and owner approval:

- remove the EC2 test-only symlink;
- restore or verify the test launcher state;
- clean approved scratch data; and
- consider removal of obsolete v3 profile files in a separate change.

## 13. File inventory

### Add in CAPE Cod

- `assets/analysis-pipelines/bactopia/bactopia-base-4.1.0.json`.
- `assets/analysis-pipelines/bactopia/ont-bactopia-4.1.0.json`.
- `assets/analysis-pipelines/bactopia/taxprofiler-kraken2-2.0.1.json`.
- `assets/etl/etl_bactopia_run_metadata.py`, if the CAPE-owned sidecar design is
  selected instead of extending the main result ETL.
- V4 ETL test fixtures under a repository test/fixture directory.
- Unit/contract tests for profile schemas, MLST, metadata, and output matching.

### Modify in CAPE Cod

- `assets/containers/nextflow-kickstart/entrypoint.sh`, only if runtime tests
  identify a needed generated-config change.
- `assets/etl/etl_bactopia_results.py`.
- `assets/etl/etl_bactopia_samples.py`.
- `assets/report/bactopia-single-sample-analysis/data_function.py`, only with
  the matching manifest/table change.
- `Pulumi.cape-cod-dev.yaml`, if Glue, profiler, EFS, Batch, or DAP registration
  changes require it. Do not edit `Pulumi.cape-cod-public.yaml`; CI/CD generates
  it from dev configuration.
- Documentation and wiki pages describing the final contract.

### Do not delete initially

- Existing v3.2.0 and dev pipeline fixtures.
- Existing historical v3 output.
- Existing v3 ETL tables or report data.
- Scratch validation data, until cleanup is separately approved.

### External additions or modifications

- External Airflow Bactopia/Kraken DAG repository: v4 invocation, QC gate, run
  metadata sidecar, profiler stage, output publication, resources, retries, and
  deployment. This is a handoff, not a CAPE Cod edit in the current scope.
- External DAG synchronization/source deployment path such as `cape-cod-env`:
  DAG source publication and DAG-level variables if required. CAPE Cod owns the
  MWAA environment configuration and deployment described in section 9.3.
- New standalone profiler repository, only if taxprofiler is rejected.
- Analysis-host AMI/bootstrap or compute configuration if host-mounted EFS is
  selected; identify the owning repository before any edit.

## 14. Definition of done

The migration is ready for owner deployment only when:

- v4 profile schemas and inheritance pass tests;
- the generated runtime config works without `-profile aws`;
- the parent and child AWS CLI path contracts are explicit and validated;
- the selected database strategy works in a production-shaped child;
- the selected Kraken2 process resource policy schedules on the target Batch
  compute environment;
- QC policy is explicit and validated;
- Bactopia publishes the v4 run manifest and complete output tree;
- v4 MLST and AMRFinderPlus pass ETL ingestion;
- report metadata and AMRFinderPlus joins pass;
- the selected profiler report parses and renders semantically;
- the external DAG contract is updated and dev-tested;
- Pulumi preview has no unexplained churn;
- rollback and historical-output behavior are documented; and
- the test EC2 instance and temporary resources are handled according to owner
  approval;
- the demo compatibility and platform generalization gates in section 10 are
  resolved or have explicit owner-approved follow-up issues.

No frontend implementation is included in this definition of done. Frontend work
may consume the stable report/API contract after the backend migration is
accepted.

## 15. Remaining branch completion sequence

This sequence is the high-level implementation path for the current branch. It
is deliberately separate from the generic execution-class and resource-
capability redesign in the local follow-on analysis.

1. Reconcile the current runtime contract.
   - Keep the parent AWS CLI path and Batch host `aws.batch.cliPath` separate.
   - Use the deployed `awsbatch` AMI host path for child staging.
   - Keep the generated shared Nextflow config as the common runtime boundary.
   - Keep the tested Kraken2 process override explicit and pipeline-scoped.

2. Select and document the tactical database bridge.
   - Use the current shared EFS database without copying it from S3.
   - Add the required EFS host mount to the relevant analysis host bootstrap or
     systemd mounter path in the AWS Batch AMI repository.
   - Resolve the filesystem and mount settings from deployment/runtime context.
   - Verify mount targets, NFS security, IAM, read-only behavior, and host
     readiness before Batch accepts work.
   - Do not implement the generic zero-to-many execution-class system in this
     branch unless the bridge proves impossible.

3. Rerun the EFS sentinel canary.
   - Use the existing ONT input and the real EFS database path.
   - Verify that a dynamic child sees `hash.k2d`, `opts.k2d`, and `taxo.k2d`.
   - Capture host, Availability Zone, mount target, requested resources, and
     staging behavior.
   - Stop on a missing mount instead of falling back to S3 staging silently.

4. Run real taxprofiler Kraken2 processing.
   - Pin `nf-core/taxprofiler` v2.0.1.
   - Enable the Kraken2-only preset.
   - Keep minimizer output disabled for the initial six-column report.
   - Use the approved EFS path and measured child allocation.
   - Persist native outputs to an isolated S3 result root.

5. Normalize and validate the profiler output.
   - Identify the native per-sample Kraken2 report.
   - Produce the stable CAPE compatibility artifact under the agreed report
     path.
   - Compare semantic rows, taxid sets, classified totals, key taxa, parser
     behavior, and renderer output against the established Bactopia baseline.
   - Preserve native taxprofiler outputs for future tool presets.

6. Complete the CAPE-owned metadata contract.
   - Choose the run-manifest sidecar or registry projection.
   - Include sample identity, run identity, input object, Bactopia version,
     Nextflow version, taxprofiler version, execution class terminology,
     database reference, output root, and QC path.
   - Keep the metadata writer in the orchestration owner unless this repository
     owns the confirmed producer.

7. Complete ETL, Glue, crawler, and report validation.
   - Run the checked-in v4 MLST and AMRFinderPlus fixtures.
   - Validate assembler, Sourmash, and MASH outputs.
   - Validate the run metadata table and `bactopia_run` joins.
   - Confirm taxprofiler report artifacts do not create accidental Bactopia ETL
     rows.
   - Validate Athena queries and HTML rendering.

8. Review CAPE-owned deployment configuration.
   - Update only `Pulumi.cape-cod-dev.yaml` if the approved bridge requires it.
   - Do not edit `Pulumi.cape-cod-public.yaml`.
   - Run `pulumi preview --diff -s <target-stack>`.
   - Reconcile every create, update, replace, or delete with this branch.
   - Do not run `pulumi up`.

9. Complete external handoffs.
   - Provide the external Airflow DAG owner the v4 invocation, QC filename,
     profiler dependency, resource policy, metadata manifest, output paths,
     retry behavior, and rollback target.
   - Keep frontend and external DAG implementation outside this repository.

10. Close the migration safely.
    - Document rollback and historical v3 behavior.
    - Review the deferred CPU/memory cost optimization after functional success.
    - Leave scratch data and temporary resources untouched until separately
      approved for cleanup.
    - Track the generic execution-class and resource-capability follow-on in its
      local design document before filing the external issue.
