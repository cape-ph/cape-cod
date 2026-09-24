---
type: analysis
title: Issue 379 migration resumption handoff
created: 2026-09-18
updated: 2026-09-23
status: current
---

Status: current Issue 379 checkpoint after commit `abad135`, the successful
2026-09-23 deployment, and the representative data-product validation. This
page supersedes older status statements in
[[analyses/bactopia-41-new-session-handoff]] and records historical handoffs
below without rewriting their source evidence.

## Current checkpoint

Completed:

- Bactopia v4.1 profiles, v4 ETL contract adapters, and trusted execution-class routing are committed.
- The standalone `nf-core/taxprofiler` v2.0.1 Kraken2 DAP is the selected replacement for Bactopia's v4 Kraken2 wrapper.
- The immutable Standard-8 Kraken2/Bracken database is published in the meta-assets bucket and the runtime export is deployed.
- The deployed DAP handler serializes DynamoDB `Decimal` process overrides through capepy's shared JSON serializer.
- The normal DAP path returned HTTP 200. The representative taxprofiler parent `f72665b0-9ff9-4e11-9ead-5ac5cd3aab2d`, Kraken2 child `104e0d80-1f4b-485f-9e79-2c851f16554d`, and MultiQC child all succeeded with exit code 0.
- The standalone taxprofiler report exists at `batch_job_scratch/issue379-taxprofiler-bactopia-v4-20260923192043/output/kraken2/standard-8/caerbannog-test-nf2604-bt410_bactopia-20260916-132854_standard-8.kraken2.kraken2.report.txt`. Its schema and semantic output remain compatible with the v3 baseline; rank-code and low-count ordering differences are expected.
- The deployed output-derived Bactopia report ETL succeeded for the v4 HTML replay. The result-clean crawler succeeded, and the corrected metadata CSV omits `bactopia_run` as a data column while retaining it as the partition.
- The stale duplicate `bactopia_run` column in the dev Glue table was repaired with owner approval. The follow-up Athena query succeeded and returned the expected v4 metadata, including Bactopia 4.1.0, Nextflow 26.04.6, input path, output root, QC path, and `--ont`.
- The deployed Aiken-era `report/get` handler was invoked directly for `micah-test-2` and returned separate `bactopia`, `kraken2`, and `rabits` HTML bodies with `createdAt` values. This confirms the multi-report body API used by the frontend.
- The asset publisher, taxprofiler database-sheet generator, edge-case tests, and transitional `cape-cod-env` handoff note are committed in `abad135`.

Validation boundary and remaining work:

- `report/get` reads pre-rendered objects from `reports/<sample_id>/`; it does not generate reports. The existing Aiken artifact bodies are present for historical samples, but the new Issue 379 v4 replay objects currently exist in result-raw/result-clean and have not been published as new `reports/<sample_id>/bactopia.html` or `kraken2.html` artifacts.
- `report/create` remains a separate on-demand path. Its deployed data Lambda currently fails because the report role lacks `s3:GetObject` access to the input-clean objects required by the `input_meta` Athena CTAS query. The defect and longer-term pre-generation work are recorded in issue #367.
- The current v4 taxprofiler raw report and CAPE ETL metadata are validated. Rendering and publishing the current v4 Kraken2 HTML artifact remains owned by the external report-generation path, not this CAPE Cod ETL change.
- The v4 crawlable run-metadata contract is now implemented through the existing Bactopia results ETL and partitioned `software_versions.csv`; legacy v3 `software_versions.yml` compatibility remains preserved.
- Clean and commit the remaining authored Issue 379 wiki checkpoint separately from the feature commit. Do not stage unrelated working-tree files.

Ownership boundaries:

- The external Airflow DAG repository owns orchestration changes.
- CAPE Cod owns the Bactopia profiles, ETL, report integration, runtime export, and DAP path.
- EFS capability implementation belongs to issue 384 / PR 385. Mixed historical evidence remains here only when it also records an issue-379 decision.

## Historical Step 1 stopping point

CAPE Cod Step 1 is committed on branch `379-migrate-from-bactopia-v320-to-v410` as:

```text
579a582 feat(bactopia): wire trusted taxprofiler Batch overrides
```

The commit contains the separate parent-container and Batch-host AWS CLI paths, trusted DAP profile process-policy propagation, the Kraken2-only `nf-core/taxprofiler` v2.0.1 profile, structured Nextflow process override rendering, and focused tests. No CAPE Cod deployment or `pulumi up` was run.

The CAPE Cod working tree now contains the uncommitted Step 2 implementation and authored wiki pages/local planning artifacts. Do not stage the whole working tree. `PLAN.md` and `extra-doc/README.nextflow-batch.md` remain local artifacts. The dev stack file is the only Pulumi stack file in scope; do not edit `Pulumi.cape-cod-public.yaml`.

## Historical AMI handoff for PR 385

The external repository is `cape-ph/aws-batch-ecs-ami`.

- Branch: `12-add-runtime-configured-efs-host-mount-readiness-for-batch-hosts`.
- Commits:
  - `3194302 chore(build): guard HashiCorp Packer executable`
  - `562bf37 feat(ami): add runtime-configured EFS host mounter`
- Pull request: https://github.com/cape-ph/aws-batch-ecs-ami/pull/13
- Reviewer requested: `mehalter`.
- Retained CAPE test AMI:
  - AMI: `ami-0415ac72712439c9f`
  - Snapshot: `snap-0cb7e5da27c4e726c`
  - Name: `awsbatch-efs-cape-test-20260918-hvm-2023.0.20250414-kernel-6.1-x86_64`

The disposable host test passed against the AMI. It injected the real EFS ID only through untracked test user data, mounted the EFS root at `/mnt/nextflow_shared_data`, and verified these files under `/mnt/nextflow_shared_data/kraken2`:

- `hash.k2d`
- `opts.k2d`
- `taxo.k2d`

The test also verified the systemd service reached `active (exited)` and the EFS TLS proxy was running. The test instance, temporary bucket, Packer builder, and earlier disposable AMIs were cleaned up. The retained AMI and snapshot are intentionally not cleaned up yet because Cape Cod needs them for the next integration test.

The AMI repository uses the mise-installed HashiCorp Packer at `/home/lp76/.local/share/mise/installs/packer/1.11.0/packer`. The repo Makefile now rejects the system `/usr/sbin/packer` name collision with `cracklib-packer`; the generated `*.hwm`, `*.pwd`, and `*.pwi` artifacts are ignored.

## Historical Step 2 implementation state

The uncommitted Cape Cod Step 2 slice now includes:

- A `taxonomic-profiling` capability-specific Batch environment using the retained AMI and an EFS host bootstrap.
- A complete `execution_routes` map for `workflow-orchestration`, `general-analysis`, and `taxonomic-profiling`.
- Bactopia v4 assigned to `general-analysis`; legacy profiles without a class retain the general queue fallback.
- All three dev Batch environments configured to use the retained AMI. The owner accepted the resulting replacements for the existing `workflows` and `analysis` compute environments, subject to preview review and the user's deployment step.
- Atomic bootstrap file writes plus an explicit mounter restart.
- The existing analysis security group reused for the dev capability pool. No new EFS security-group rule is proposed in this slice.

The final preview succeeded with:

```text
20 creates
10 updates
2 replacements
484 unchanged
```

The replacements are the existing `ccd-pvsl-analysis-btch-cmpt-env` and
`ccd-pvsl-workflows-btch-cmpt-env`, caused by the AMI update. No deployment was
performed. The complete output is at `/tmp/cape-cod-step2-final-preview.txt`.

Local validation passes: 22 focused tests, Python compilation, Ruff, JSON
parsing, LSP diagnostics, and `git diff --check`.

## Next execution phase

The next Issue 379 work is the representative data-product validation:

1. Run Bactopia v4.1 with the representative ONT input and the accepted QC policy.
2. Feed the required Bactopia v4 QC output into the selected taxprofiler Kraken2 DAP.
3. Publish or capture the v4 run metadata sidecar under the agreed crawlable prefix.
4. Verify CAPE ETL ingestion, crawler tables, `bactopia_run` and sample joins, Athena queries, and HTML report rendering.
5. Compare Kraken2 output semantically against the established representative report, not byte-for-byte.
6. Update this handoff with final evidence after the path succeeds.

The EFS sentinel, host bootstrap, and EFS resource lifecycle remain historical
handoff material for PR 385 or issues 381/380, not the current Issue 379 gate.

## Boundaries and safety

- Do not run `pulumi up`, deploy, destroy, or delete the retained AMI without explicit owner approval.
- Keep the retained AMI until Cape Cod integration is complete or the owner approves cleanup.
- External Airflow DAG, frontend, profiler, and `aws-batch-ecs-ami` code beyond the reviewed PR are separate scope.
- The generic zero-to-many execution-class/resource registry and future Snakemake support remain follow-on design work.
- Use semantic Kraken2 comparisons, not byte equality.
- Preserve v3 fixtures and historical outputs.

## Read first on resumption

1. This page.
2. [[analyses/bactopia-41-cape-cod-implementation-design]].
3. [[analyses/cape-pipeline-execution-classes-and-resource-capabilities]].
4. [[analyses/kraken2-and-bactopia-41-migration-findings]].
5. The AMI PR and issue #12.
6. `extra-doc/README.nextflow-batch.md` only as an exploratory decision aid, not as committed user documentation.
