---
type: synthesis
title: "Resources Subsystem (capeinfra/resources/)"
slug: resources-subsystem
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["resources", "reusable", "aws", "subsystem"]
---

# Resources Subsystem (`capeinfra/resources/`)

Reusable, general-purpose CAPE construct wrappers over common AWS primitives.
These are the building blocks the higher-level subsystems (meta, datalake,
swimlane, pipeline) compose. Every class subclasses `CapeComponentResource` (see
[[concepts/capepulumi-base-classes]]) and most expose a `PolicyEnum` +
`policies` for IAM (see [[entities/iam-module]]).

## Modules and constructs

- [[entities/objectstorage-module]] - `Bucket` and `VersionedBucket`: S3 bucket
  wrappers with policy groups, object upload helpers, and content reads.
- [[entities/database-module]] - `DynamoTable` (with item-insert helper and
  read/write policy groups) and `RDSInstance` (Postgres, subnet group,
  credentials, policy groups).
- [[entities/cape-rest-api-module]] - `CapeRestApi`: API Gateway REST API from a
  rendered OpenAPI spec, with endpoint/authorizer Lambdas, logging, proxy roles,
  and VPC-endpoint stage deployment.
- [[entities/compute-module]] - Lambda layer hierarchy (`CapeLambdaLayer` and
  subclasses for python/gh-release/aws-managed layers) plus
  `CapeLambdaFunction`.
- [[entities/loadbalancer-module]] - `AppLoadBalancer`: an internal ALB with
  helpers to add static-app, EC2-instance, and API targets.
- [[entities/queue-module]] - `SQSQueue`: a FIFO SQS queue with put/consume
  policy groups.
- [[entities/certs-module]] - `BYOCert`: an ACM certificate created from
  bring-your-own PEM files.

## Cross-cutting patterns

- Config-driven defaults via `default_config`; nested reads via
  `CapeConfig.get`.
- Named IAM statement groups (`PolicyEnum` -> `policies`) consumed by
  `get_inline_role`.
- `register_outputs({...})` to publish stack outputs.
- Length-constrained names; `desc_name` tag carries the human-readable name.

Related: [[syntheses/cape-cod-architecture-overview]],
[[syntheses/pipeline-subsystem]].
