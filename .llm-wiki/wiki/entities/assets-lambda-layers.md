---
type: entity
title: "assets: lambda layers (assets/lambda-layers/)"
slug: assets-lambda-layers
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["lambda-layers", "capepy", "weasyprint", "assets"]
---

# assets: lambda layers (`assets/lambda-layers/`)

Build inputs for the Lambda layers referenced by `cape-cod:meta.function_layers`
and built by `CapeMeta.create_function_layers` using the layer classes in
[[entities/compute-module]].

## `capepy/`

The `capepy` runtime SDK layer (the abstraction used by nearly all deployed
Python; see [[syntheses/assets-subsystem]]).

- `capepy-3.0.0-py3-none-any.whl` - the built wheel (also listed in
  `requirements.txt`).
- `capepy_layer.zip` - the packaged layer archive.
- `update_layer_zip.sh` - rebuilds `capepy_layer.zip`: unzips the wheel into
  `./python/lib/python3.10/site-packages` and zips it as a layer (python3.10
  layout).

## `capi-all/requirements.txt`

- Pins `capepy==3.0.0`. The layer for the capi API handlers.

## `report-gen/requirements.txt`

- Pins `Jinja2==3.1.6` and `weasyprint==66.0`. The layer for report generation
  (see [[entities/assets-report]]).

`python`-type layers are built locally by pip-installing these requirements;
`gh-release`-type layers are fetched from GitHub releases (see
[[entities/compute-module]]).

Related: [[syntheses/assets-subsystem]], [[entities/capemeta-module]],
[[entities/compute-module]].
