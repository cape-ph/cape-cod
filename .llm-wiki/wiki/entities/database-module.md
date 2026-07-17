---
type: entity
title: "database module (capeinfra/resources/database.py)"
slug: database-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["dynamodb", "rds", "postgres", "database", "resources"]
---

# database module (`capeinfra/resources/database.py`)

Datastore wrappers: a DynamoDB table wrapper and an RDS (Postgres) instance
wrapper.

## `DynamoTable(CapeComponentResource)`

- `type_name` = `capeinfra:resources:database:DynamoTable`.
- `PolicyEnum` - read/write policy groups.
- Constructor:
  `DynamoTable(name, hash_key, idx_attrs, range_key=None, **kwargs)`. Creates an
  `aws.dynamodb.Table`; `idx_attrs` are the attribute definitions needed for
  keys/indexes (only index-relevant attributes are declared, matching DynamoDB's
  schemaless nature).
- `policies` - named IAM statement groups for table access.
- `add_table_item(name, item)` - inserts a `TableItem`.

Used for the workflow metadata registry (`WorkflowMetaRegistry`) and elsewhere
registries need key/value document storage. The DAP registry uses a raw
`aws.dynamodb.Table` directly rather than this wrapper (see
[[entities/dap-registry-module]]).

## `RDSInstance(CapeComponentResource)`

- `type_name` = `capeinfra:resources:database:RDSInstance`.
- `PolicyEnum` - access policy groups.
- Constructor:
  `RDSInstance(name, subnet_group, db_name="cape_env_db", instance_class=aws.rds.InstanceType.T4_G_SMALL, engine="postgres", engine_version="18.2", port=5432, username="postgres", extra_rds_kwargs=None, **kwargs)`.
  Creates the RDS instance within a supplied subnet group; extra RDS kwargs are
  passed through.
- `policies` - IAM statement groups for the instance.

Instantiated by `PrivateSwimlane.create_env_rds_instance` (see
[[entities/private-swimlane-module]]).

The `env-db-rds` instance is the ABAC/OPA environment database - it is created
empty here, then migrated by cape-cod-env using the cape-cod-db schema. See
[[syntheses/abac-opa-cross-repo]].

Related: [[syntheses/resources-subsystem]],
[[concepts/capepulumi-base-classes]], [[entities/iam-module]],
[[syntheses/abac-opa-cross-repo]].
