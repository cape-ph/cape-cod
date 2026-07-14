---
type: entity
title: "meta module (capeinfra/meta/capemeta.py)"
slug: capemeta-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["meta", "cognito", "lambda-layers", "assets", "reports"]
---

# meta module (`capeinfra/meta/capemeta.py`)

System-wide scaffolding created once per stack. `CapeMeta` is instantiated at
import time in `capeinfra/__init__.py` as `meta` (see
[[syntheses/cape-cod-architecture-overview]]). Configured from the
`cape-cod:meta` config section (see [[concepts/pulumi-config-structure]]).

This module defines four classes.

## `CapeMeta(CapeComponentResource)`

The top-level meta construct.

- `type_name` = CAPE meta namespace; has a `PolicyEnum`.
- Constructor builds the shared automation assets bucket (a `VersionedBucket`,
  see [[entities/objectstorage-module]]) - the system-wide object store for
  reusable ETL scripts and Lambda functions - and orchestrates the other meta
  pieces.
- `create_function_layers(layer_specs)` - builds the configured Lambda layers
  from `cape-cod:meta.function_layers` using the layer hierarchy in
  [[entities/compute-module]] (`python` layers built locally, `gh-release`
  layers fetched). The resulting layers are passed by name to downstream
  constructs.
- `policies` - IAM statement groups.

## `CapePy(CapeComponentResource)`

- Constructor: `CapePy(assets_bucket, **kwargs)` - manages the `capepy` Lambda
  layer (the wheel ships in `assets/lambda-layers/capepy/...`, see
  `requirements.txt`) published into the assets bucket.

## `CapePrincipals(CapeComponentResource)`

Cognito-based identity: user pool, groups, users, external IdPs (SAML), and an
identity pool. (Class name is historical - a code note says it made sense when
it only added users/groups.)

- `default_config` / `type_name` / `policies`.
- Handles IdP config (`_handle_idpcfg`, `_construct_saml_provider_details`,
  `add_idps`), principals (`add_principals`, `_add_cape_group`,
  `_add_cape_user`, `_add_user_to_group`), identity pool (`add_identity_pool`,
  `default_trust_policy`), a user-attribute store
  (`create_user_attribute_store`, `_add_user_attrs_items`, `_parse_user_attrs`),
  loading users/groups from files (`load_groups_file`, `load_users_file`), and
  app clients (`add_client`).

## `CapeCannedReports(CapeComponentResource)`

- Constructor: `CapeCannedReports(assets_bucket, function_layers, **kwargs)` -
  manages "canned" report generation: a report store bucket
  (`create_canned_report_store`), per-report resources
  (`_create_canned_report`), and report metadata (`_store_canned_report_meta`).
  Report assets live in `assets/report/` (see [[syntheses/assets-subsystem]]).

Related: [[syntheses/cape-cod-architecture-overview]],
[[concepts/capepulumi-base-classes]], [[entities/iam-module]],
[[entities/compute-module]].
