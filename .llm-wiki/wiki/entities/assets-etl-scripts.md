---
type: entity
title: "assets: ETL scripts (assets/etl/)"
slug: assets-etl-scripts
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["etl", "glue", "assets", "bioinformatics"]
---

# assets: ETL scripts (`assets/etl/`)

AWS Glue ETL scripts. Each instantiates `capepy.aws.glue.EtlJob` (see
[[syntheses/assets-subsystem]]), reads a source object (`etl_job.get_src_file()`
/ `etl_job.parameters["OBJECT_KEY"]`), transforms it, and writes clean output to
the sink. Run by `EtlJob` Pulumi constructs (see
[[entities/pipeline-data-module]]) and triggered via the SQS->Glue Lambda (see
[[entities/assets-trigger-functions]]).

## Per-file

- `etl_bactopia_results.py` (163 lines) - parses a subset of bactopia pipeline
  output (MLST `mlst.tsv`, AMRFinderPlus `amrfinderplus[-proteins].tsv` - name
  varies by bactopia version, `software_versions.yml`) from the
  `merged-results/` and `software-versions/` prefixes, partitioned by
  `bactopia_run`.
- `etl_bactopia_samples.py` (102 lines) - parses per-sample bactopia files
  (sample TSV, mash TXT, sourmash TXT) matched by regex patterns.
- `etl_fasta_fastq.py` (139 lines) - handles FASTA/FASTQ inputs using `pyfastx`;
  detects type via `fastx_format_check`. TODO: "GET ME MOVED TO MY OWN REPO."
- `etl_gphl_cre_alert.py` (70 lines) - parses an Epi/HAI CRE alert `.docx`
  (single table via `python-docx`), extracts report date and rows, writes CSV.
  Mirrored from `cape-ph/etl-gphl-cre-alert`.
- `etl_gphl_sequencing_alert.py` (68 lines) - parses an Epi/HAI sequencing
  report `.pdf` (report date via `pypdf`, tables via `tabula`), writes CSV.
  Mirrored from `cape-ph/etl-gphl-sequencing-alert`.
- `etl_seqarchive.py` (145 lines) - processes a `tar.gz` sequencing archive
  (`meta.json` + gzipped fastx files under `sequencing/`); augments metadata and
  concatenates fastx into a single gzipped output keyed by sample id + UTC
  timestamp.
- `etl_tnl_alert.py` (124 lines) - parses a Tennessee health-lab Epi/HAI alert
  `.xlsx` (via `pandas`) into a fixed output column schema (`OUT_COL_NAMES`).

## Notes

- These run in the Glue/`capepy` environment, so `pyrightconfig.json` ignores
  `assets/etl/**`. Do not expect repo-venv imports to resolve.
- Naming/namespacing of clean output keys is inconsistent and flagged with TODOs
  across several scripts.

Related: [[syntheses/assets-subsystem]], [[entities/pipeline-data-module]],
[[entities/datalake-module]].
