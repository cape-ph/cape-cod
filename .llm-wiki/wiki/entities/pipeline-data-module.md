---
type: entity
title: "pipeline/data module (DataCrawler, EtlJob)"
slug: pipeline-data-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["glue", "crawler", "etl", "pipeline"]
---

# pipeline/data module (`capeinfra/pipeline/data.py`)

AWS Glue building blocks for cataloging and transforming data lake data.

## `DataCrawler(CapeComponentResource)`

- `type_name` = `capeinfra:pipeline:...` crawler namespace.
- `default_config` supplies crawler defaults (e.g. schedule/behavior).
- Constructor: `DataCrawler(name, buckets, db, *, prefix=None, **kwargs)` -
  creates an `aws.glue.Crawler` over one or more `VersionedBucket`s targeting a
  Glue `CatalogDatabase`, with an inline role (see [[entities/iam-module]]).
  `prefix` scopes the crawled path.

## `EtlJob(CapeComponentResource)`

- `type_name` = ETL job namespace; has a `PolicyEnum`.
- `default_config` supplies ETL defaults.
- Constructor:
  `EtlJob(name, src_bucket, sink_bucket, script_bucket, *, default_args={}, **kwargs)` -
  creates an `aws.glue.Job` that runs an ETL script (stored in `script_bucket`)
  reading from `src_bucket` and writing to `sink_bucket`. `default_args` sets
  Glue job arguments.
- `policies` - IAM statement groups for the job.

ETL scripts themselves live in `assets/etl/` (see
[[syntheses/assets-subsystem]]) and are uploaded to the script bucket.
Tributaries configure crawlers and ETL jobs per bucket (see
[[entities/datalake-module]]).

Related: [[syntheses/pipeline-subsystem]], [[concepts/capepulumi-base-classes]],
[[entities/objectstorage-module]].
