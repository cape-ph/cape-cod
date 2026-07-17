---
type: synthesis
title: "ABAC Resource Export - Implementation Plan (cape-cod)"
slug: abac-resource-export-implementation-plan
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-14
tags:
    [
        "abac",
        "opa",
        "resource-export",
        "pulumi",
        "cape-cod-db",
        "cape-cod-env",
        "plan",
    ]
---

# ABAC Resource Export - Implementation Plan (cape-cod)

> IMPLEMENTED 2026-07-14. Decisions locked: O1 = no cape-cod-db dependency
> (plain dicts); O2 = use the real AWS-evaluated bucket names in exact `s3://`
> paths (logical-identity reconcile via `attributes` still applies for churn);
> O3 = whole-bucket; O4 = `capeinfra/authz/export.py`; O5 = `display_name`
> defaults to code, `description` null (no config copy added yet). Delivered:
> `capeinfra/authz/export.py` (pure `_category_for_bucket_id`, `_display_label`,
> `_resource_record`, `_assemble_export`, `_collect_export_inputs` +
> `build_resource_export`), `Tributary.__init__` metadata capture in
> `capeinfra/datalake/datalake.py`, `pulumi.export("abac_resource_export", ...)`
> in `__main__.py`, `.mise.toml` task `export-abac-resources`, and
> `tests/test_authz_export.py` (10 tests, all pass; ruff clean). NOT yet done:
> `pulumi preview` could not run - this sandbox has no network egress to the S3
> state backend (`s3://cape-pulumi-state/cape-cod`, `dial tcp ... i/o timeout`),
> so preview must be run by the user in a networked environment. See
> [[sources/pulumi-runtime-test-boto3-and-output-plumbing-split]] for why the
> `@pulumi.runtime.test` integration test was replaced with a runtime-free
> `_collect_export_inputs` test.

Ready-to-execute plan for adding the resource JSON export to cape-cod. Written
2026-07-13 after verifying the completed cape-cod-db ABAC rework (migration
`010c0bff0b83`) against the local `abac_schema_rework` branch. Start here in the
morning.

## 1. What is our goal

CAPE authorizes access with ABAC, OPA as the decision engine, and the
environment Postgres RDS (`cape_env_db`) as the source of truth for
authorization facts. The near-term demo: a user asks "which S3 locations can I
read/write?" and upload/download is gated by an OPA decision.

Three-repo loop (see [[syntheses/abac-opa-cross-repo]]):

- `cape-cod` (this repo): provisions RDS + buckets, and MUST emit a JSON export
  of the resources it deployed.
- `cape-cod-db`: owns the schema/migrations (rework DONE, see below).
- `cape-cod-env`: runs migrations and (planned) a "database update" script that
  ingests the export and reconciles it into the schema.

This repo's single responsibility: produce an accurate JSON export of the
deployed datalake resources. No DB writes, no diff, no reconcile, no OPA
bundle - those live in the other repos.

## 2. What cape-cod-db looks like now (verified)

The rework landed exactly as designed. Authoritative sources: `models.py` +
migration `010c0bff0b83` + `fixtures/test/test_data.sql`. The old `notes/` are
gone; cape-cod-db now uses its own `.llm-wiki/` (see its
`concepts/abac-authorization-design` and `entities/database-schema`).

- `Resource` is now a PURE CATALOG. The `access_type` column was DROPPED. A
  resource row records only WHAT exists: `resource_type`, unique
  `resource_identifier`, `display_name`, nullable `tributary_id`, JSONB
  `attributes`. GIN index on `attributes`.
- `Tributary`: unique `name` + unique `code`, `description` (Text, nullable),
  self-FK `parent_id`, JSONB `attributes`.
- New `ResourceGrant`: per-(subject, resource, action) row. Subject is exactly
  one of `user_id` / `tributary_id` (CHECK
  `ck_resourcegrant_exactly_one_subject`); `resource_id` FK ON DELETE CASCADE;
  one action per row via `access_type`; UNIQUE
  `(user_id, tributary_id, resource_id, access_type)` with `NULLS NOT DISTINCT`;
  `granted_by`, `expires_at`.
- Effective access = UNION of role-based tributary defaults and explicit grants,
  evaluated default-deny in Rego. `attributes.category` (`raw_uploads`,
  `clean_uploads`, `raw_results`, `clean_results`, ...) is the stable
  descriptor; policy maps category -> default action (raw -> write, clean ->
  read).
- Canonical `resource_type` for S3 is `"s3"`. S3 `resource_identifier` is the
  `s3://bucket/path` form, not the ARN (ARN goes in `attributes`).

Consequence for the export: it populates `Tributary` + `Resource` (catalog)
ONLY. It carries NO `access_type` and NO grants. Access is derived from
`category` and assigned via memberships/grants (admin/Cognito), all downstream.

## 3. How the export moves us toward the goal

The `Resource` table cannot be hand-maintained: bucket names are AWS-generated
at deploy time and change as infra evolves. The export is the automated bridge
that keeps the catalog truthful: Pulumi already holds both the tributary
abstraction and the live bucket Outputs, so it is the only place that can map
"HAI input-raw bucket" -> its real `s3://` identifier + ARN + category. Emitting
that as JSON lets cape-cod-env reconcile the DB to match reality, which is the
prerequisite for OPA to make correct decisions about real buckets.

## 4. Cleanest, simplest, minimal solution

### 4.1 Export shape (no access_type)

```json
{
    "version": "1.0",
    "pulumi_stack": "cape-cod-dev",
    "tributaries": [
        {
            "code": "hai",
            "name": "HAI",
            "description": "Healthcare-associated infections ...",
            "resources": [
                {
                    "resource_type": "s3",
                    "resource_identifier": "s3://<physical-bucket-name>/",
                    "display_name": "HAI raw input uploads",
                    "attributes": {
                        "bucket": "<physical-bucket-name>",
                        "arn": "arn:aws:s3:::<physical-bucket-name>",
                        "category": "raw_uploads",
                        "bucket_role": "input-raw",
                        "tributary_code": "hai",
                        "environment": "cape-cod-dev",
                        "managed_by": "cape-cod-pulumi"
                    }
                }
            ]
        }
    ]
}
```

Resources are grouped under their tributary; the env script upserts the
tributary (by `code`), then upserts each resource with the resolved
`tributary_id`. `tributary_code` + `bucket_role` are duplicated into
`attributes` deliberately so the env reconcile can key on LOGICAL identity even
if the physical bucket name (and thus `resource_identifier`) changes on a bucket
replacement. `managed_by` bounds what the reconcile is allowed to delete.

Bucket-id -> category (and policy's derived action, for reference only):

| bucket_id    | category      | derived action |
| ------------ | ------------- | -------------- |
| input-raw    | raw_uploads   | write          |
| input-clean  | clean_uploads | read           |
| result-raw   | raw_results   | write          |
| result-clean | clean_results | read           |

Non-conforming bucket ids: emit with `category: "other"` + `log.warn`; policy
grants nothing by default (safe). Internal buckets (catalog, athena results) are
NOT exported in v1.

### 4.2 Code structure (new module `capeinfra/authz/export.py`)

Split pure shaping from Pulumi Output plumbing so the semantics are
unit-testable without Pulumi:

- `CATEGORY_BY_BUCKET_ID: dict[tuple[str, str], str]` and
  `_category_for_bucket_id(bucket_id) -> str` - pure.
- `_resource_record(*, bucket_name, bucket_arn, bucket_id, tributary_code, display_name, stack) -> dict` -
  pure; builds one resource dict.
- `build_resource_export(dlh, stack) -> pulumi.Output[dict]` - iterates
  `dlh.tributaries`, and per bucket uses
  `Output.all(name=vb.bucket.bucket, arn=vb.bucket.arn).apply(...)` to fill in
  the deploy-time strings, assembling the nested dict. Returns an Output.

Bucket Output access is confirmed: `VersionedBucket.bucket` is the
`aws.s3.Bucket`; `.bucket.bucket` = physical name Output, `.bucket.arn` = ARN
Output.

### 4.3 Tributary config + model wiring

Add optional human fields per tributary in `Pulumi.cape-cod-dev.yaml` (and any
other stack configs), backward-compatible:

```yaml
tributaries:
    - name: hai # -> Tributary.code (short, already drives AWS names)
      display_name: "HAI" # -> Tributary.name (human)
      description: "..." # -> Tributary.description
      buckets: ...
```

In `capeinfra/datalake/datalake.py` `Tributary.__init__`, capture (the config
wrapper is `CapeConfig.get(*keys, default)`):

```python
self.code = self.config.get("name")
self.display_name = self.config.get("display_name", default=self.code)
self.description = self.config.get("description", default=None)
```

`Tributary.buckets` is `dict[str, VersionedBucket]` keyed by bucket_id
(`input-raw`, etc.), which is what the export iterates.

### 4.4 Wire the stack export

In `__main__.py` (top-level program wiring; `capeinfra.data_lakehouse` is built
in `capeinfra/__init__.py`):

```python
import pulumi
import capeinfra
from capeinfra.authz.export import build_resource_export

pulumi.export(
    "abac_resource_export",
    build_resource_export(capeinfra.data_lakehouse, capeinfra.CAPE_STACK_NS),
)
```

### 4.5 Getting the local `cape-cod-export.json` (MVP)

Do NOT write files as a side effect inside the program (applies do not run on
`preview`, and file-writes-in-programs are a smell). Use the idiomatic path:

```bash
pulumi stack output abac_resource_export --json > cape-cod-export.json
```

Add a mise/Makefile task for it. Stack outputs only populate after `pulumi up`,
so the file is produced on a real deploy machine; agents cannot `up` here, so
local verification is via unit tests (below). A later `--push-to-s3` option is
additive; the cape-cod-env importer should accept a local path OR an `s3://`
path regardless.

### 4.6 Tests (mirror `tests/test_datalake.py`)

- Pure-function tests (no Pulumi) carry the semantics: `_category_for_bucket_id`
  for all four bucket roles + a non-conforming id; `_resource_record` asserts
  the exact key set, `s3://<name>/` identifier form, and attributes contents.
- One `@pulumi.runtime.test` over `build_resource_export(mock_datalake, ...)`
  resolving the Output and asserting structure: three tributary codes (`hai`,
  `genomics`, `seqauto`), four resources each, correct `bucket_role` and
  `category`, and presence of `resource_identifier`/`arn`. Under mocks the
  physical bucket name may resolve to `None`/logical-name, so keep string-exact
  identifier assertions in the pure tests and assert structure/keys here.

## 5. Pitfalls and how to overcome them

1. Outputs are not strings. Physical names/ARNs are `Output`s; assemble the dict
   inside `.apply()` and return an `Output`. Never `str()` an Output or build
   the JSON at module scope.
2. Outputs resolve only after `up`. The file cannot be generated locally in the
   agent sandbox (no creds, no `up`). Rely on unit tests for correctness; the
   file is produced on deploy machines.
3. Mocks resolve bucket names loosely. Keep exact-string assertions in the pure
   tests; the Pulumi-coupled test asserts shape only.
4. Physical bucket names are volatile. Config leaves bucket `name:` empty, so
   AWS auto-names buckets (with a random suffix) and a bucket REPLACEMENT
   changes the name -> changes `resource_identifier` -> the env reconcile would
   see delete+insert. Mitigations: (a) carry `tributary_code` + `bucket_role` in
   `attributes` so cape-cod-env can match on logical identity and UPDATE the
   identifier instead of churning; and/or (b) consider setting stable explicit
   bucket names in config. Flag for the env-script design.
5. `resource_type`/field-name drift. The contract is "export JSON keys ==
   cape-cod-db model field names + `attributes.category` vocabulary." If
   cape-cod does NOT import cape_cod_db (recommended, see open question O1),
   cape-cod-env validates the incoming JSON against the models and fails loudly
   on drift.
6. cape-cod-db is not released yet. It sits on branch `abac_schema_rework`,
   version still `0.3.0`, CHANGELOG not updated for `010c0bff0b83`. cape-cod-env
   cannot pin the new schema until cape-cod-db cuts a release (>= 0.4.0). This
   is a cape-cod-db action on the critical path; our export work does not block
   on it, but the end-to-end sync does.
7. Scope creep. Do not emit grants, access, memberships, or per-user data. The
   export is tributary org units + resource catalog only.
8. Tooling. New module must pass black + isort + ruff at 80 cols and pyright
   basic; run `pulumi preview` + pytest, never `pulumi up`.

## 6. Open questions (resolve first thing)

- O1 (biggest): Does cape-cod take a dependency on `cape-cod-db`?
  RECOMMENDATION: NO. The export is pure catalog data; emit plain dicts with the
  agreed keys and keep the ORM stack (sqlmodel/alembic/psycopg2) out of the IaC
  venv. cape-cod-env already must depend on cape-cod-db and is the right place
  to validate the JSON against the models. This reverses the earlier lean
  ("consume the package API") now that the export writes nothing and holds no
  access logic. Confirm.
- O2: Stable bucket names? Leaving names AWS-generated makes
  `resource_identifier` volatile (pitfall 4). Accept logical-identity reconcile
  in cape-cod-env, or set explicit stable bucket names in datalake config?
  RECOMMENDATION: logical-identity reconcile now (cheaper, no infra change);
  revisit stable names if churn hurts.
- O3: Export granularity - whole-bucket `s3://<bucket>/` (recommended, matches
  our separate-bucket-per-role infra and how OPA sees requests) vs prefix-level.
  Confirm whole-bucket.
- O4: Where to place the new module - `capeinfra/authz/export.py` (recommended,
  room to grow to non-S3 resource types) vs a datalake-local helper. Confirm.
- O5: Human `display_name`/`description` values for `hai`, `genomics`, `seqauto`
  - who provides the copy? Default `display_name` to the code and
      `description` to null until provided.

## 7. Execution order (morning)

1. Confirm O1-O5.
2. Add `display_name`/`description` capture in `Tributary.__init__` + populate
   the three tributaries in `Pulumi.cape-cod-dev.yaml`.
3. Add `capeinfra/authz/export.py` (pure builders + `build_resource_export`).
4. Wire `pulumi.export("abac_resource_export", ...)` in `__main__.py`.
5. Add tests in `tests/test_authz_export.py`; run `pulumi preview` + pytest;
   black/isort/ruff/pyright.
6. Add a mise/Makefile task for
   `pulumi stack output ... > cape-cod-export.json`.
7. Hand off the export shape + O1 decision to the cape-cod-env session for the
   database-update script, and note the cape-cod-db release dependency (pitfall
   6).

## Related pages

- [[syntheses/abac-opa-cross-repo]]
- [[entities/database-module]]
- [[concepts/coding-style-and-tooling]]
- [[concepts/testing-and-pulumi-preview-workflow]]
