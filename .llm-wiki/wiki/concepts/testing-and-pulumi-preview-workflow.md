---
type: concept
title: "Testing and Pulumi Preview Workflow"
slug: testing-and-pulumi-preview-workflow
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["testing", "pulumi", "preview", "pytest", "safety", "workflow"]
---

# Testing and Pulumi Preview Workflow

CAPE Cod deploys live, shared infrastructure. Local verification is limited and
safety-critical. This page defines what agents may and may not do.

## Hard safety rule: never `pulumi up`

Agents must never run `pulumi up` (or any deploy/destroy). Deployment against
the live AWS account is the user's responsibility. The environment is live
infrastructure an agent cannot push to or introspect easily. Until a proper
mocked-AWS unit-testing setup exists, local testing is confined to:

1. `pulumi preview` - to confirm the program resolves and to inspect the planned
   resource graph and outputs.
2. `pytest` - the small mock-based test suite under `tests/`.

## `pulumi preview` as the primary check

`pulumi preview` compiles the Pulumi program and computes the resource diff
without applying it. Use it to verify that config resolves, constructs
instantiate, and outputs are what you expect. Per `README.md`, first-time setup
is roughly:

- `pulumi login --local` (state on local filesystem).
- `pulumi stack init cape-cod-public` (or select an existing stack).
- The public stack's encryption key is `insecure`; you will be prompted for it.
- `grep -i set_secret Pulumi.cape-cod-public.yaml` to find unset secrets; set
  them with `pulumi config set --secret <key> <val>` as needed for a clean
  preview.
- `pulumi preview` should complete with no errors and list the resources that
  would be created.

Prefer running `pulumi preview` against a local, non-production stack. Do not
run it in a way that mutates a shared/live stack's config.

## The pytest suite

Small, mock-based, under `tests/`. Run with `pytest` (VSCode is configured for
pytest against `tests`).

- `tests/conftest.py` sets `pulumi.runtime.set_mocks(PulumiMock())` and loads
  `Pulumi.cape-cod-dev.yaml`'s `config` into the `PULUMI_CONFIG` env var
  (JSON-encoded) for the session. Fixtures `mock_meta` and `mock_datalake`
  instantiate `CapeMeta` and `DatalakeHouse` under mocks.
- `PulumiMock` returns inputs as outputs for `new_resource` and empty results
  for `call` - so tests assert on declared inputs/structure, not real AWS.
- Tests use `@pulumi.runtime.test` and assert on resource properties via
  `Output.apply`. Examples: `test_capemeta.py` checks the automation assets
  bucket has versioning enabled; `test_datalake.py` checks the catalog bucket
  type.

To extend coverage, follow this pattern: add a mock fixture if needed, decorate
with `@pulumi.runtime.test`, and assert on `Output` values via `.apply`.

### Gotcha: the suite requires valid AWS credentials (verified 2026-07-13)

The Pulumi mocks only intercept Pulumi resource registration and provider
`call`s - they do NOT intercept direct `boto3` calls made in Python during
construct construction. Building `CapeMeta` / `DatalakeHouse` performs real S3
`GetObject` calls (e.g. asset/layer handling), so the suite needs valid,
unexpired AWS credentials in the environment.

- With expired/absent credentials, both `test_capemeta.py::test_asset_bucket`
  and `test_datalake.py::test_catalog` fail with
  `botocore.exceptions.ClientError: ... (ExpiredToken) ... GetObject ...`. This
  is an environment/credentials issue, not a code regression - refresh
  credentials before trusting a pytest result.
- Layer fixtures pip-install `capepy==3.0.0` during setup (visible in captured
  stdout); this is expected.
- Numerous `DeprecationWarning`s about `s3.BucketV2` / `BucketVersioningV2` are
  benign pulumi_aws version-drift noise.

## CI behavior

`.github/workflows/cape.yml` runs reusable `python_checks.yml@v1` (with
`pytest: false`) and `general_checks.yml@v1` from the `cape-ph/.github` repo. So
CI does NOT currently run the pytest suite - run it locally.
`.github/workflows/pulumi.yml` regenerates `Pulumi.cape-cod-public.yaml` from
the dev config with secrets scrubbed to `SET_SECRET` and opens a PR. A release
workflow runs on tags. See [[concepts/pulumi-config-structure]].

## Future direction

A proper unit-testing setup with a mocked AWS environment is a desired future
step that would widen what can be verified locally. Until then, `pulumi preview`
plus the mock pytest suite are the ceiling.

Related: [[syntheses/cape-cod-architecture-overview]],
[[concepts/coding-style-and-tooling]], [[concepts/pulumi-config-structure]].
