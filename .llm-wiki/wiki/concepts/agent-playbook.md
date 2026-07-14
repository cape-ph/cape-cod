---
type: concept
title: "Agent Playbook (Start Here)"
slug: agent-playbook
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["playbook", "workflow", "start-here", "safety", "onboarding"]
---

# Agent Playbook (Start Here)

The single entry point for working in CAPE Cod. Read this first, then follow the
links. This wiki is a lens for orientation - it summarizes structure and intent
but never substitutes for reading the exact source before an edit.

## What this repo is

CAPE Cod is the Pulumi (Python) IaC program for the CAPE platform. Import flow:
Pulumi -> `__main__.py` -> `import capeinfra` (which instantiates `CapeMeta` and
`DatalakeHouse` as import side effects) -> `PrivateSwimlane`. See
[[syntheses/cape-cod-architecture-overview]]. Everything is config-driven
through `CapeComponentResource` + `CapeConfig` (see
[[concepts/capepulumi-base-classes]], [[concepts/pulumi-config-structure]]).

## Standard task loop

1. Orient: `wiki_recall` with task terms; open the relevant subsystem synthesis
   and module entity page.
2. Locate: use the page's class/method map to find the file and symbol.
3. Read the real code: `read_symbol` / `read` the exact body before editing.
   Bodies are intentionally not stored in the wiki and drift over time.
4. Edit minimally: smallest correct change, matching existing conventions (see
   [[concepts/coding-style-and-tooling]]).
5. Validate: `pulumi preview` on a local stack and `pytest` (see
   [[concepts/testing-and-pulumi-preview-workflow]]).
6. Record: `wiki_retro` durable insights, `wiki_observe` running notes; update
   the affected page if structure changed.

## Hard rules

- NEVER run `pulumi up` or any deploy/destroy. Local verification is
  `pulumi preview` (local, non-production stack) + `pytest` only.
- Tooling is fixed: Python -> black + isort at 80 cols; YAML/JSON/Markdown ->
  Prettier; types -> Pyright `basic`. Do NOT add ruff, flake8, biome, eslint, or
  mypy. Do not change CI/tooling without explicit instruction.
- Edit files in place; keep diffs tightly scoped. Do not touch generated files,
  `assets-untracked/`, or the wiki's `raw/`, `meta/`, `outputs/` layers.
- `assets/**` is deployment-time runtime code, some vendored from other repos
  (see [[syntheses/assets-subsystem]]); a fix here may need to be carried
  upstream, and `capepy` is a separate package.

## Map of the territory

- Base classes: [[concepts/capepulumi-base-classes]]
- Meta / identity / layers / reports: [[entities/capemeta-module]]
- Data lake (tributaries, catalog): [[entities/datalake-module]],
  [[syntheses/pipeline-subsystem]], [[entities/pipeline-data-module]]
- Networking environment: [[entities/scoped-swimlane-module]],
  [[entities/private-swimlane-module]]
- Resources: [[syntheses/resources-subsystem]] (objectstorage, database, queue,
  certs, compute, loadbalancer, cape-rest-api)
- IAM helpers: [[entities/iam-module]]; utilities: [[entities/util-modules]]
- Runtime assets (ETL, handlers, triggers, containers, pipelines, user-data,
  reports, layers): [[syntheses/assets-subsystem]]
- API surface: [[entities/assets-api-authorizer-and-spec]] (route table),
  [[entities/assets-capi-handlers]], [[entities/cape-rest-api-module]]

## Known landmines

- The default API authorizer allows everything (test stub) - a real security
  gap, not production authz. See [[entities/assets-api-authorizer-and-spec]].
- capi handlers set `Access-Control-Allow-Origin: *` (temporary CORS bypass,
  ISSUE #141).
- `submit_dap_run.py` has hardcoded Batch queue/job-definition names (TODO to
  move to env vars).
- Resource names are length-constrained: `stack_ns` and `disemvowel` shorten
  names deliberately; do not lengthen resource names casually.
- CI does not run pytest - run it locally.
- The pytest suite needs valid, unexpired AWS credentials: construction makes
  real S3 `GetObject` calls that the Pulumi mocks do not intercept. Expired
  creds surface as `ClientError ... (ExpiredToken) ... GetObject`. See
  [[concepts/testing-and-pulumi-preview-workflow]].

Related: [[syntheses/cape-cod-architecture-overview]].
