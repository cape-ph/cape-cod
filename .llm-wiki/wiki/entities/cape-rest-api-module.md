---
type: entity
title: "api module (capeinfra/resources/api.py)"
slug: cape-rest-api-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["api-gateway", "rest-api", "openapi", "lambda", "resources"]
---

# api module (`capeinfra/resources/api.py`)

## `CapeRestApi(CapeComponentResource)`

Builds an API Gateway REST API from a rendered OpenAPI spec, wiring endpoint
Lambdas, authorizers, logging, proxy roles, and a VPC-endpoint-fronted stage.

- `type_name` = CAPE REST API namespace.
- Constructor:
  `CapeRestApi(name, api_name, spec_path, stage_suffix, env_vars, legacy_resource_grants, policy_statements, vpc_endpoint, domain_name, *, lambda_vpc_cfg=None, **kwargs)`.
  The Lambdas are placed in the VPC so they can reach MWAA; a code TODO flags
  the VPC config as hastily added and wanting design review.

Build steps (private methods):

- `_configure_logging()` - CloudWatch logging for the API.
- `_create_api_ep_lambdas(legacy_res_grants, policy_statements)` - creates the
  endpoint handler Lambdas (handlers live in `assets/api/capi/handlers/`; see
  [[syntheses/assets-subsystem]]), granting them the requested resource access.
- `_create_aws_proxy_roles()` - roles for API Gateway AWS-service proxy
  integrations.
- `_render_spec()` - renders the OpenAPI Jinja template
  (`assets/api/capi/capi-openapi-301.yaml.j2`) via [[entities/util-modules]]
  `get_j2_template_from_path`.
- `_create_rest_api()` - creates the `aws.apigateway.RestApi` from the rendered
  spec.
- `_create_api_authorizer_lambdas(res_grants=None)` - creates authorizer
  Lambda(s) (default authorizer at
  `assets/api/authz/default_apigw_authorizer.py`).
- `_deploy_stage(domain_name)` - deploys the stage (named with `stage_suffix`)
  and associates the VPC endpoint / domain.

Instantiated by `PrivateSwimlane._deploy_api` (carries a TODO for ISSUE #61) and
fronted by an ALB API target (see [[entities/private-swimlane-module]],
[[entities/loadbalancer-module]]). IAM statements come from
[[entities/iam-module]] (`get_api_statements`, `get_vpce_api_invoke_policy`).

Related: [[syntheses/resources-subsystem]],
[[concepts/capepulumi-base-classes]].
