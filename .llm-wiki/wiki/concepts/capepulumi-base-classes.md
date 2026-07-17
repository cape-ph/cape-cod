---
type: concept
title: "capepulumi Base Classes"
slug: capepulumi-base-classes
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["pulumi", "base-classes", "config", "conventions"]
---

# capepulumi Base Classes

`capepulumi.py` (repo root) is the foundation module for the whole project. It
defines the config object and the base component-resource class that every CAPE
construct subclasses. It is intentionally a standalone top-level module with no
module-level state: because `capeinfra/__init__.py` instantiates resources as an
import side effect, any stateful top-level code here would create circular
import/instantiation problems. Keep this module free of top-level state.

## `update_dict(base, delta)`

Recursive deep-merge helper. Merges `delta` into `base`, recursing into nested
dicts, skipping `None` values in `delta`, and adding new keys. Non-dict `base`
is replaced by `delta`. Backs `CapeConfig.update`.

## `CapeConfig(dict)`

A `dict` subclass representing a CAPE configuration object with deep-merge and
nested-get semantics.

- Constructor accepts either a mapping or a string. A string is treated as a
  Pulumi config key and resolved via `Config(config_name).require_object(...)`
  (default config name `cape-cod`). A `default` mapping can be supplied and the
  provided config is deep-merged on top of it.
- `get(*keys, default=None)` walks an arbitrarily nested path and returns the
  value or `default`; mapping results are re-wrapped as `CapeConfig`.
- `update(delta)` applies `update_dict` in place.

`DEFAULT_CONFIG_NAME = "cape-cod"` is the Pulumi config namespace used across
the project. See [[concepts/pulumi-config-structure]].

## `CapeComponentResource(ComponentResource)`

The base class for all CAPE constructs. Extends `pulumi.ComponentResource` with
configuration handling and a descriptive-name convention.

Constructor kwargs beyond Pulumi's:

- `desc_name` - a human-readable descriptive name added to resource tags
  (`desc_name`), because real resource names are length-constrained.
- `config` - a mapping, or a string naming a Pulumi config section to pull.
- `config_name` - the Pulumi config section name (used only when `config` is a
  string).

It builds
`self._config = CapeConfig(config, config_name=..., default=self.default_config)`
and calls `super().__init__(self.type_name, ...)`.

Abstract/overridable members subclasses provide:

- `type_name` (abstract property) - the Pulumi type token for namespacing, e.g.
  `capeinfra:resources:queue:SQSQueue`.
- `default_config` (abstract property) - the default config dict merged under
  supplied config.
- `policies` (abstract property) - a dict mapping policy names to lists of
  `aws.iam.GetPolicyDocumentStatementArgsDict`. Only meaningful for constructs
  that expose IAM policies; those pair it with a nested `PolicyEnum(str, Enum)`
  of supported policy names. See [[entities/iam-module]] for how these
  statements become roles.

## Conventions this establishes

- Every construct = a subclass of `CapeComponentResource` with a `type_name`.
- Config flows top-down: parents read a section and pass sub-config to children;
  `default_config` supplies defaults; `CapeConfig.get` reads nested paths
  safely.
- Constructs that grant access publish named policy statement groups via
  `policies` + `PolicyEnum`, consumed by IAM role helpers.
- `register_outputs({...})` is called by most constructs to declare stack
  outputs.

Related: [[syntheses/cape-cod-architecture-overview]],
[[concepts/pulumi-config-structure]], [[entities/iam-module]].
