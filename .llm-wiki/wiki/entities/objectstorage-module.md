---
type: entity
title: "objectstorage module (capeinfra/resources/objectstorage.py)"
slug: objectstorage-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["s3", "bucket", "storage", "resources"]
---

# objectstorage module (`capeinfra/resources/objectstorage.py`)

S3 bucket wrappers used throughout CAPE (data lake buckets, script/asset
buckets, static-web buckets, canned-report stores).

## `Bucket(CapeComponentResource)`

- `type_name` = `capeinfra:resources:objectstorage:Bucket` (namespacing).
- `PolicyEnum` - supported named policy groups for the bucket.
- Constructor:
  `Bucket(name, bucket_type="", bucket_name=None, cors_rules=None, **kwargs)`.
  Creates the underlying `aws.s3.Bucket`, optional CORS rules, and tags.
- `policies` - returns named policy statement groups (e.g. read/write access)
  for use with [[entities/iam-module]] role helpers.
- `add_object(name, key, source, import_id=None, **obj_kwargs)` - uploads an
  object (from a Pulumi `Asset`/`Archive`) to the bucket at `key`; supports
  importing an existing object by id.
- `get_object_contents(key, log_missing_keys=False)` - reads object contents
  (uses `boto3`), returning contents or handling missing keys.

## `VersionedBucket(Bucket)`

- `type_name` = `capeinfra:resources:objectstorage:VersionedBucket`.
- Subclass of `Bucket` that additionally enables S3 versioning
  (`versioning_configuration.status == "Enabled"`). This is asserted in
  `tests/test_capemeta.py` for the automation assets bucket.

## Usage

- The automation assets bucket in `CapeMeta` is a `VersionedBucket` (see
  [[entities/capemeta-module]]).
- Data lake raw/clean buckets and Tributary buckets are built on these (see
  [[entities/datalake-module]]).
- Lambda layer publishing uses `VersionedBucket` object storage (see
  [[entities/compute-module]]).

Related: [[syntheses/resources-subsystem]],
[[concepts/capepulumi-base-classes]], [[entities/iam-module]].
