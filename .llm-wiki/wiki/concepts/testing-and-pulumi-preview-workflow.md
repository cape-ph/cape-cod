---
type: concept
title: "Testing and Pulumi Preview Workflow"
slug: testing-and-pulumi-preview-workflow
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-21
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

## Reviewing the `--diff` before a deploy

Whenever a change touches the Pulumi program or the `assets/**` it deploys,
`pulumi preview --diff` is a required deployment-preparation step, run and
reviewed before the user performs the real deploy. The point is to confirm the
planned change matches the intended scope, not just that the program compiles.

- Run `pulumi preview --diff` against the target stack (e.g. `-s cape-cod-dev`).
  `--diff` expands per-resource property changes so create/update/replace/delete
  and the specific fields are visible, not just a summary count.
- Reconcile every reported action against the changes actually made in the
  branch. Each create/update should trace to a real edit; there should be no
  unexplained churn.
- Treat replacements or deletions of shared resources as stop-and-investigate
  signals. A replace on a stateful resource (bucket, database, queue) can be
  destructive; understand why before the user deploys.
- Only once the diff is understood and matches the intended change does the user
  run the deploy. Agents still never run `pulumi up` - the review is the agent's
  job, the deploy is the user's.

### Known benign recurring drift

Some resources show up in nearly every `cape-cod-dev` preview regardless of the
branch under review. These are expected and are not a reason to hold a deploy on
their own - when a preview contains only these plus the branch's intended
changes, the diff is clean:

- `cognito/identityProvider` `GTRI-SSO` (`cape-idp-SAML-GTRI-SSO`): its
  `providerDetails` (SAML `ActiveEncryptionCertificate`,
  `SLORedirectBindingURI`, `SSORedirectBindingURI`) recompute to `[unknown]` on
  essentially every preview. This SAML metadata always recomputes; it is
  expected.
- `docker-build:index:Image` `nextflow_kickstart`: its `contextHash` changes
  regularly, which shows as an image rebuild. This is normal churn, not
  necessarily a concern. The rebuild cascades to the batch `jobDefinition`
  (`ccd-pvsl-nextflow-jobdef` revision bump) and the IAM policy that references
  that revision ARN (`ccd-pvsl-nextflow-jobdef-pssrl-plcy`), so those two
  updates typically ride along with it.

Still scan them each time - the point is they are known-benign by default, not
that they should be ignored. Anything outside this set and the branch's own
changes is what warrants investigation.

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
