---
type: entity
title: "iam module (capeinfra/iam.py)"
slug: iam-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["iam", "roles", "policies", "aws", "helpers"]
---

# iam module (`capeinfra/iam.py`)

A module of free functions (no classes) that build IAM policy statements, roles,
and instance profiles reused across CAPE constructs. This is where the
`policies` / `PolicyEnum` statement groups published by constructs (see
[[concepts/capepulumi-base-classes]]) get assembled into concrete roles.

## Functions

- `get_service_assume_role(srvc)` - builds an assume-role policy document for
  one or more AWS service principals (e.g. `lambda.amazonaws.com`).
- `get_bucket_reader_policy(buckets, principal=None)` - read access statements
  for one or more S3 buckets, optionally scoped to a principal.
- `get_bucket_web_host_policy(buckets, vpce_id=None)` - S3 static-website
  hosting access, optionally restricted to traffic arriving through a given VPC
  endpoint.
- `get_vpce_api_invoke_policy(vpc_id=None, vpce_id=None)` - allows API Gateway
  invoke through a VPC endpoint. NOTE (in code): currently allows invoke to all
  APIs reachable via the VPC endpoint - a known over-broad grant.
- `get_api_statements(grants)` - generalized API access statement builder;
  evolved from DAP-API-specific code (carries a TODO to generalize further).
- `add_resources(statements, *arns)` - appends resource ARNs onto a list of
  statement dicts.
- `aggregate_statements(statements)` - flattens/aggregates statement lists.
- `get_inline_role(name, desc_name, srvc_prfx, assume_role_srvc, statements=None, srvc_policy_attach=[], opts=None)`
  - the central role factory. Creates an `aws.iam.Role` with an inline policy
      from `statements` and optional managed-policy attachments. A code NOTE
      explains it is a function (not a class) because the pattern recurs in many
      places (lambda trigger functions, crawlers, etc.).
- `get_instance_profile(name, role, name_suffix=None)` - wraps a role in an EC2
  instance profile.

## How it is used

Constructs expose named policy statement groups via their `policies` property
keyed by a `PolicyEnum`. Callers select the statements they need and pass them
to `get_inline_role` to mint a scoped role, often attaching AWS managed policies
alongside. `get_instance_profile` is used for EC2/Batch instance roles.

Statement types are typed as `aws.iam.GetPolicyDocumentStatementArgsDict`.

Known follow-ups referenced in code: tighter scoping of the VPC-endpoint API
invoke policy, and generalizing `get_api_statements`.

Related: [[concepts/capepulumi-base-classes]],
[[syntheses/resources-subsystem]], [[syntheses/pipeline-subsystem]],
[[syntheses/cape-cod-architecture-overview]].
