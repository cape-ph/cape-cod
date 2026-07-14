---
type: concept
title: "Pulumi Config Structure"
slug: pulumi-config-structure
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["pulumi", "config", "yaml", "secrets", "stacks"]
---

# Pulumi Config Structure

CAPE Cod is entirely configuration-driven. Stack config lives in
`Pulumi.<stack>.yaml` under the top-level `config:` mapping and is read through
`CapeConfig` (see [[concepts/capepulumi-base-classes]]). The Pulumi config
namespace is `cape-cod` (`DEFAULT_CONFIG_NAME`), so construct config sections
are addressed as `cape-cod:<section>`.

## The two committed stack files

- `Pulumi.cape-cod-dev.yaml` - the source-of-truth reference config. It is
  heavily commented and documents every supported option inline; read it as the
  canonical config reference (`README.md` "Config Values" points here).
- `Pulumi.cape-cod-public.yaml` - an auto-generated public mirror of the dev
  config with all secret values scrubbed to `SET_SECRET`. Do not hand-edit it;
  `.github/workflows/pulumi.yml` regenerates it from the dev config using `yq`
  and opens a PR on changes to `main`. Its encryption key is `insecure`.

New stacks are made with
`pulumi stack init <name> --copy-config-from cape-cod-public`.

## Top-level config sections (dev config)

- `deployment:meta` (anchored `&depmet`) - deployment-wide metadata reused
  elsewhere, e.g. `stage-suffix` (`"dev"`, `"prod"`) used in API paths and stage
  names.
- `aws:region` - single deployment region (e.g. `us-east-2`); CAPE currently
  supports one region.
- `cape-cod:aws` - `availability-zones` (e.g. `az1`/`az2`, each anchored for
  reuse in subnet configs).
- `cape-cod:meta` - consumed by `CapeMeta` (see [[entities/capemeta-module]]).
  Includes `function_layers` (Lambda layer specs of type `python` built locally
  from a requirements file, or `gh-release` pulled from a GitHub release asset),
  and Cognito/principals and canned-report config.
- `cape-cod:swimlanes` - consumed by `PrivateSwimlane` (see
  [[entities/private-swimlane-module]]). Under `private`: `domain`, `tls`,
  `cidr-block`, `subnets`, API/app definitions, VPN, etc.
- `cape-cod:datalakehouse` - consumed by `DatalakeHouse` (see
  [[entities/datalake-module]]): `bucket_cors_policies` and `tributaries`.

## Concrete sub-key reference

The dev file is the authoritative, fully-commented reference; this skeleton is a
navigation aid to the key blocks (line numbers drift, so grep by key).

- `cape-cod:meta`
  - `function_layers[]` - each item: `name` (unique; S3-object-key-safe),
      optional `cleanup_tmp`, `type_args` (`type: python|gh-release|aws`;
      `python` needs `reqs`, `gh-release` needs `uri`+`tag`+`asset`, `aws` needs
      `arn`), and optional `args` (`description`, `compatible_runtimes`).
  - `principals` - `idps`, `groups`, `users` inline, plus `idps_extra` /
      `groups_extra` / `users_extra` pointing at files under
      `assets-untracked/principals/` (external IdP YAML, groups/users CSV).
  - `glue` - `etl` settings.
  - `report` - `template_prefix` (e.g. `reports/templates`) and `reports`.
- `cape-cod:swimlanes.private` (see [[entities/private-swimlane-module]])
  - Networking: `cidr-block` (e.g. `10.0.0.0/16`), `subnets`, `domain`
      (`cape-dev.org`), `subdomain`.
  - `tls` - `dir` (`assets-untracked/tls/...`), `ca-cert`, `server-cert`,
      `server-key` (see [[entities/certs-module]]).
  - `env-db-rds` - `engine` (`postgres`), `engine_version`, `db_name`,
      `instance_class`, `port`, `username`, `extra-rds-values` (see
      [[entities/database-module]]).
  - `api` / `apis`, `compute` / `container_images` / `jobs`, `instance-apps` /
      `instances` / `environments`, `stage`.
  - `vpn` - `cidr-block` (e.g. `10.254.0.0/22`), `transport-proto` (`udp`),
      `pub-key`.
- `cape-cod:datalakehouse` (see [[entities/datalake-module]])
  - `bucket_cors_policies` - named CORS policies (e.g. `mpu_policy` with
      `allowed_methods` / `allowed_headers` / `expose_headers` /
      `allowed_origins`).
  - `tributaries` - per-tributary buckets, crawlers, and ETL config.

## Conventions

- YAML anchors/aliases (`&depmet`, `&az1`, `<<: *anchor`) are used heavily to
  keep the config DRY. Preserve/extend anchors rather than duplicating blocks.
- Constructs pull their section by passing a string to `CapeComponentResource`
  (`config="meta"` / `"swimlanes"` / `"datalakehouse"`), which resolves it via
  `Config("cape-cod").require_object(section)`, then merge it over
  `default_config`.
- Nested reads go through `CapeConfig.get("a", "b", default=...)`, which never
  raises on missing intermediate keys.

## Secrets

- Encrypted values use Pulumi's secret mechanism:
  `pulumi config set --secret <key> <value>` (prompts for the stack encryption
  key).
- The public stack marks values that must be provided with `SET_SECRET`; find
  them with `grep -i set_secret Pulumi.cape-cod-public.yaml` before a preview.
- New secret keys can appear on upstream pulls; re-check for `SET_SECRET` after
  pulling.

Related: [[syntheses/cape-cod-architecture-overview]],
[[concepts/capepulumi-base-classes]],
[[concepts/testing-and-pulumi-preview-workflow]].
