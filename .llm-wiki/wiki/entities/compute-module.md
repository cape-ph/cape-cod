---
type: entity
title: "compute module (capeinfra/resources/compute.py)"
slug: compute-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["lambda", "lambda-layers", "compute", "resources"]
---

# compute module (`capeinfra/resources/compute.py`)

Lambda functions and a layer-publishing class hierarchy. Layers are built or
fetched, published to a `VersionedBucket`, and referenced by functions.

## Lambda layer hierarchy

- `CapeLambdaLayer` (abstract base) - defines `lambda_layer` and the abstract
  `_make_layer`.
- `CapeManagedLambdaLayer` - base for layers CAPE builds/publishes to object
  storage. Handles deciding whether to (re)build a local layer
  (`should_deploy_local_layer`), running build commands (`_run_command`),
  publishing assets to the bucket (`publish_layer_assets`, `_publish_asset`),
  and cleanup (`maybe_cleanup`). Keyed by a `remote_zip_key`.
- `CapePythonLambdaLayer` - builds a python layer by pip-installing a
  requirements file; compares a published pip manifest (`_pip_list_layer`,
  `_do_layers_match`, `remote_manifest_key`) to avoid rebuilds when unchanged.
  Config type `python` (see [[concepts/pulumi-config-structure]]
  `function_layers`).
- `CapeGHReleaseLambdaLayer` - uses a prebuilt layer archive downloaded from a
  GitHub release (`layer_archive_uri`), via
  `util/repo.get_github_release_artifact` (see [[entities/util-modules]]).
  Config type `gh-release`.
- `CapeAwsManagedLambdaLayer` - wraps an existing AWS-managed layer ARN via an
  inner `LambdaLayerShim` (no build/publish).

The layer specs come from `cape-cod:meta.function_layers` and are built up by
`CapeMeta.create_function_layers` (see [[entities/capemeta-module]]); the
resulting layers are passed by name to downstream constructs that need them.

## `CapeLambdaFunction(CapeComponentResource)`

- `type_name` = CAPE Lambda function namespace; has a `PolicyEnum`.
- Constructor:
  `CapeLambdaFunction(name, role, code, handler, layers=None, architectures=None, description=None, memory_size=None, timeout=None, runtime="python3.10", logging_config=None, environment=None, **kwargs)`.
  Wraps `aws.lambda_.Function` with sensible CAPE defaults (python3.10 runtime).
- `policies` - IAM statement groups for the function.

Used pervasively: API endpoint/authorizer Lambdas (see
[[entities/cape-rest-api-module]]), data lake ETL trigger Lambdas, etc.

Related: [[syntheses/resources-subsystem]],
[[concepts/capepulumi-base-classes]], [[entities/iam-module]].
