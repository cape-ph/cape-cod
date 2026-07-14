---
type: entity
title: "assets: analysis pipeline fixtures (assets/analysis-pipelines/)"
slug: assets-analysis-pipelines
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags:
    ["analysis-pipelines", "dap", "bactopia", "nextflow", "fixtures", "assets"]
---

# assets: analysis pipeline fixtures (`assets/analysis-pipelines/`)

JSON fixtures defining the Data Analysis Pipelines (DAPs) loaded into the DAP
registry at deploy time by `DAPRegistry.load_pipeline_assets` (see
[[entities/dap-registry-module]]). Each file is rendered as a Jinja template
(with `aws_region`) then loaded as JSON.

## Fixture schema

Each fixture is a pipeline profile with keys such as:

- `pipelineType` (e.g. `nextflow`), `pipelineName`, `pipelineId`,
  `pipelineDescription`, `project`, `version`.
- `parametersSchema` - a JSON Schema (draft 2020-12) describing the pipeline's
  parameters (with `const`/`default` values, titles, types).
- `submission` - how parameters are encoded for submission (e.g.
  `optionsFieldName: nextflowOptions`, `encoding: cli-string`).
- `inherits` - optional list of parent profile stems. The registry resolves
  inheritance iteratively; inherited schemas are referenced via
  `parametersSchema.$defs` and `$ref`. This is why the loader processes profiles
  in dependency order.

## `bactopia/` fixtures

Bactopia pipeline variants, each in a pinned (`3.2.0`) and a `dev` version:

- `bactopia-base-3.2.0.json` / `bactopia-base-dev.json` - base Bactopia
  execution (profile `aws`, conda/shared-data volumes).
- `kraken2-bactopia-3.2.0.json` / `kraken2-bactopia-dev.json` - Kraken2
  workflow; `inherits` the base profile; adds `--wf kraken2`, `--kraken2_db`,
  cpu/memory params.
- `ont-bactopia-3.2.0.json` / `ont-bactopia-dev.json` - Oxford Nanopore (ONT)
  workflow variant.

These run as Nextflow jobs on AWS Batch via the kickstart container (see
[[entities/assets-containers]], [[entities/batch-module]]); `submit_dap_run`
schedules them (see [[entities/assets-capi-handlers]]).

Related: [[syntheses/assets-subsystem]], [[entities/dap-registry-module]].
