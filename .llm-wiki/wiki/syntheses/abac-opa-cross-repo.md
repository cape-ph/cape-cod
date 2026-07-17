---
type: synthesis
title: "ABAC/OPA Cross-Repo Interaction (cape-cod, cape-cod-db, cape-cod-env)"
slug: abac-opa-cross-repo
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags:
    [
        "abac",
        "opa",
        "rds",
        "cross-repo",
        "cape-cod-db",
        "cape-cod-env",
        "authorization",
    ]
---

# ABAC/OPA Cross-Repo Interaction

CAPE's Attribute-Based Access Control (ABAC) with OPA spans three repos. This
page maps how they interact so work can proceed without re-deriving the flow.
The authoritative design lives in cape-cod-db's own `.llm-wiki`
(`concepts/abac-authorization-design`, `entities/database-schema`); the old
`notes/` structure there has been retired. This page records the concrete wiring
and current implementation status as verified 2026-07-13. For the cape-cod
export work specifically, see
[[syntheses/abac-resource-export-implementation-plan]].

## The three repos

- `cape-cod` (this repo) - Pulumi IaC. Provisions the empty RDS Postgres
  instance and the OPA EC2 instance; will export resource metadata for sync.
- `cape-cod-db` (`../cape-cod-db`) - a Python library (SQLModel + Alembic) that
  is the canonical DB schema and migrations. Distributed as a wheel
  (`cape_cod_db`), consumed as a dependency by cape-cod-env.
- `cape-cod-env` (`../cape-cod-env`) - Ansible. Runs the DB migrations against
  the provisioned RDS and deploys environment features (workflows).

## Handoff 1: cape-cod provisions the RDS (empty)

`PrivateSwimlane.create_env_rds_instance()` builds an `RDSInstance` (see
[[entities/database-module]], [[entities/private-swimlane-module]]) from
`cape-cod:swimlanes.private.env-db-rds` (see
[[concepts/pulumi-config-structure]]):

- Postgres, `db_name=cape_env_db`, `username=postgres`, `port=5432`.
- `manage_master_user_password=True` -> AWS manages the master password in
  Secrets Manager (the instance logs the secret name). If a `password` is set in
  `extra-rds-values`, AWS password management is turned off and the password
  must instead be supplied in the cape-cod-env deployment.
- The instance is created EMPTY - no schema. Schema is applied later by
  cape-cod-env using cape-cod-db migrations.

Outputs the next repo needs: the RDS endpoint hostname and the master-password
secret name.

## Handoff 2: cape-cod-env migrates the schema

`cape-cod-env.yaml` imports `cape_env_db.yaml` (DB migration play) then runs the
`cape_env_workflows` role. The DB play (all tasks run locally,
`ansible_connection=local`):

1. Requires exactly one of `db_password` (vaulted) or `db_password_secret_name`
   (name of the AWS-managed RDS secret). With a secret name it fetches
   `<secret>.password` via `amazon.aws.aws_secret`.
2. Builds `conn_str = postgresql://{db_username}:{dbpass}@{db_host}/{db_name}`.
3. Locates the installed `cape_cod_db` package's `alembic.ini`, checks the
   current DB revision, and runs `alembic upgrade {{ db_revision }}` (default
   `head`) if not already there.

Dev inventory (`inventories/cape-cod-dev/group_vars/cape_env_db_hosts.yaml`)
pins `db_host` (the RDS endpoint, e.g.
`ccd-pvsl-env-rds-rdsinst.<...>.us-east-2.rds.amazonaws.com`),
`db_username=postgres`, a vaulted `db_password_secret_name`,
`db_name=cape_env_db`, `db_revision=head`.

CRITICAL version coupling: cape-cod-env must have the matching `cape-cod-db`
version installed. `db_revision: head` resolves against the INSTALLED package -
an out-of-date package silently skips (thinks it is already at head) or fails on
an unknown revision id. Bump `cape-cod-db` in cape-cod-env `requirements.txt`
before deploying schema changes.

## The ABAC schema (cape-cod-db)

`cape_cod_db/models.py` (SQLModel; all tables inherit `CapeModel` ->
`created_at` / `last_edited`):

- `User` - core identity (from Cognito): `first_name`, `last_name`, unique
  `email`.
- `Tributary` - organizational unit that owns resources: unique `name`/`code`,
  optional `parent_id` (self-FK hierarchy), JSONB `attributes`. No S3 path
  arrays - access is defined only via `Resource` + `ResourceGrant` records.
- `UserTributary` - M2M membership (PK `user_id`+`tributary_id`) with `role`
  (member/admin/viewer), `granted_at`/`granted_by`, optional `expires_at`. This
  membership is the core ABAC attribute.
- `Resource` - generic, platform-agnostic PURE CATALOG: `resource_type`
  (indexed), unique `resource_identifier`, `display_name`, nullable
  `tributary_id`, JSONB `attributes` (GIN indexed). The `access_type` column was
  DROPPED in the rework; a resource records only WHAT exists, never WHO can
  access it. One table for S3/EC2/Lambda/app/etc. Every tributary gets 4
  standard S3 resources (raw/clean x uploads/results).
- `ResourceGrant` - per-(subject, resource, action) grant. Subject is exactly
  one of `user_id` / `tributary_id` (CHECK
  `ck_resourcegrant_exactly_one_subject`); `resource_id` FK ON DELETE CASCADE;
  one action per row via `access_type`; UNIQUE
  `(user_id, tributary_id, resource_id, access_type)` with `NULLS NOT DISTINCT`;
  `granted_by`, `expires_at`. Effective access = UNION of role-based tributary
  defaults and these grants, default-deny in Rego; `attributes.category` maps to
  a default action (raw -> write, clean -> read).
- `UserAttribute` - flexible per-user key/value attributes (e.g. `user_status`,
  `is_admin`, `clearance_level`) with optional `source`
  (ad/saml/manual/computed) for non-tributary authorization.

Current migration head: `010c0bff0b83` ("abac per-subject resource grants": adds
`resourcegrant`, drops `resource.access_type`) on top of `6919c61ea401`
(tributary/user_tributary/resource/user_attribute). As of 2026-07-13 this is on
the local `abac_schema_rework` branch, unreleased (package still 0.3.0) - a
cape-cod-db release is required before cape-cod-env can pin it. Migrations run
via `capedb`/`alembic`; the DB URL resolves from the alembic config or a
`DB_URL` env var (`cape_cod_db/database.py`).

## The intended ABAC/OPA runtime flow

1. An API request hits a capi handler (see [[entities/assets-capi-handlers]]);
   the app queries Postgres for the user's tributaries and attributes.
2. The app POSTs an authorization input to OPA (`POST /v1/data/cape/authorize`
   with `{user, action, resource}`).
3. OPA evaluates Rego policies against a data bundle and returns `allow`.
4. The app enforces the decision.

Data sync (design): Postgres -> JSON snapshot -> OPA bundle (tar.gz), OPA polls
and hot-reloads. Resource metadata originates in Pulumi: `cape-cod` exports a
resource JSON, an Ansible sync script in `cape-cod-env` ingests it into the
`Resource` table.

## OPA instance (cape-cod)

The OPA server runs on an EC2 instance whose user-data is `opa.j2` (see
[[entities/assets-instance-user-data]]). That template already configures OPA to
pull a versioned `authz` bundle from a GitHub releases URL with polling
(`min_delay_seconds`/`max_delay_seconds`), and notes an optional S3-backed
bundle service for the future. So OPA bundle consumption is wired; bundle
GENERATION from Postgres is not.

## Implementation status (verified 2026-07-13)

Done / present:

- RDS instance provisioning in cape-cod (empty Postgres).
- ABAC schema + Alembic migrations in cape-cod-db (through `6919c61ea401`).
- cape-cod-env DB migration play (Secrets Manager password -> conn string ->
  `alembic upgrade head`).
- OPA instance user-data pulling a GitHub-hosted `authz` bundle.

Done since first mapping:

- cape-cod-db ABAC rework (migration `010c0bff0b83`): `Resource` -> pure
  catalog, new `ResourceGrant` per-subject grant table. cape-cod-db migrated its
  own docs from `notes/` to `.llm-wiki`.

Not yet built (the gaps to plan around):

- No `pulumi.export` of resource/tributary metadata in cape-cod (grep confirms
  no stack exports) - the sync source does not exist yet. Concrete plan filed at
  [[syntheses/abac-resource-export-implementation-plan]].
- No Ansible resource-sync script in cape-cod-env (only `cape_env_workflows`
  role + the DB migration play exist).
- No OPA bundle generator (Postgres -> JSON -> bundle).
- No Rego policies in-repo, and no OPA-gating in the capi handlers yet.
- `UserAttribute` table timing was "under review" in the design notes but is now
  present in `models.py`/migrations.

## Constraints to respect

- cape-cod: never `pulumi up`; use `pulumi preview` + pytest (see
  [[concepts/testing-and-pulumi-preview-workflow]]); black+isort at 80,
  Prettier, Pyright basic (see [[concepts/coding-style-and-tooling]]).
- cape-cod-db: SQLModel; migrations via Alembic only (never bypass); keep
  `fixtures/test/test_data.sql` + `cleanup_test_data.sql` in sync with schema;
  it uses ruff + black + isort + pyright and Poetry. Read its `notes/*.md` first
  (its AGENTS.md mandates this).
- cape-cod-env: Ansible; black+isort 80; keep `cape-cod-db` version current in
  `requirements.txt` before schema deploys.

Related: [[syntheses/cape-cod-architecture-overview]],
[[entities/database-module]], [[entities/private-swimlane-module]],
[[entities/assets-instance-user-data]], [[concepts/agent-playbook]].
