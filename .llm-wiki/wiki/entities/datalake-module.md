---
type: entity
title: "datalake module (capeinfra/datalake/datalake.py)"
slug: datalake-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["datalake", "glue-catalog", "tributary", "s3", "etl"]
---

# datalake module (`capeinfra/datalake/datalake.py`)

The data lake. `DatalakeHouse` is instantiated at import time in
`capeinfra/__init__.py` as `data_lakehouse` (see
[[syntheses/cape-cod-architecture-overview]]). Configured from
`cape-cod:datalakehouse` (see [[concepts/pulumi-config-structure]]).

This module defines three classes.

## `DatalakeHouse(CapeComponentResource)`

- `type_name` = data lake house namespace.
- Constructor sets up the house and its shared catalog.
- `configure_data_catalog()` - creates the shared catalog bucket and
  `CatalogDatabase` (a Glue catalog database) used across all tributaries.
- `configure_tributaries()` - iterates configured tributaries and creates a
  `Tributary` for each.

## `CatalogDatabase(CapeComponentResource)`

- `type_name` = catalog database namespace.
- Constructor: `CatalogDatabase(name, bucket, location="database", **kwargs)` -
  wraps an `aws.glue.CatalogDatabase` backed by an S3 location. Shared by
  tributary crawlers so all cataloged data lands in one Glue catalog.

## `Tributary(CapeComponentResource)`

A configurable data domain - the core data-lake abstraction. Each tributary has
its own raw and clean object storage and feeds the shared catalog.

- `type_name` = tributary namespace.
- Constructor:
  `Tributary(name, catalog_bucket, etl_attrs_ddb_table, crawler_attrs_ddb_table, aws_region, *, cors_policies=None, **kwargs)`.
  (A code TODO wants a cleaner way to pass around cors policies and function
  layers, possibly a registry.)
- `filter_buckets(prefix=["input","result"], suffix=["clean","raw"])` - selects
  the tributary's buckets by id prefix/suffix.
- `configure_bucket(bucket_id, crawler_attrs_ddb_table)` - creates a bucket and
  its Glue `DataCrawler` (see [[entities/pipeline-data-module]]), recording
  crawler attributes in DynamoDB.
- `configure_etl(etl_attrs_ddb_table)` - creates `EtlJob`s for the tributary,
  recording ETL attributes in DynamoDB.
- `configure_sqs_lambda_target(jobs)` - wires an SQS queue (see
  [[entities/queue-module]]) to a Lambda that dispatches ETL jobs.
- `configure_src_bucket_notifications(etl_attrs_ddb_table)` - sets up S3 -> SQS
  notifications on source buckets so new objects trigger the ETL pipeline.

The ETL attribute and crawler attribute DynamoDB tables let runtime Lambdas look
up which ETL/crawler applies to a given object (handlers in `assets/`; see
[[syntheses/assets-subsystem]]).

Related: [[syntheses/cape-cod-architecture-overview]],
[[syntheses/pipeline-subsystem]], [[entities/objectstorage-module]],
[[entities/database-module]], [[concepts/capepulumi-base-classes]].
