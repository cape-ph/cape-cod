---
type: entity
title: "loadbalancer module (capeinfra/resources/loadbalancer.py)"
slug: loadbalancer-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["alb", "load-balancer", "networking", "resources"]
---

# loadbalancer module (`capeinfra/resources/loadbalancer.py`)

## `AppLoadBalancer(CapeComponentResource)`

An application load balancer (internal to the swimlane VPC) with helpers to
register three kinds of targets: S3 static apps, EC2 instance apps, and API
Gateway stages (all reached through a VPC endpoint).

- `type_name` = CAPE ALB namespace.
- Constructor: `AppLoadBalancer(name, vpc_id, subnet_ids, **kwargs)` - creates
  the `aws.lb.LoadBalancer` across the given subnets.
- `next_rule_priority` - monotonic listener-rule priority allocator.
- `add_listener(port, proto, acmcert=None)` - adds/reuses a listener; HTTPS
  listeners attach an ACM cert (see [[entities/certs-module]]).
- `_add_target_group(...)`, `_add_target_group_attachments(...)`,
  `_get_listener(...)`, `_get_nic_attr_tuple(...)` - internal helpers for target
  group creation, attachment, and network-interface resolution.
- `add_static_app_target(bucket, vpc_ep, sa_name, sa_short_name, ...)` - routes
  to an S3-hosted static site via a VPC endpoint.
- `add_instance_app_target(instance, app_name, app_short_name, fqdn, ...)` -
  routes to an EC2 instance app, with health checks and HTTP->app forwarding.
- `add_api_target(vpc_ep, api_stage_name, api_short_name, ...)` - routes to an
  API Gateway stage through a VPC endpoint.

Code TODOs note significant shared boilerplate across the three `add_*_target`
methods that should be factored out.

Instantiated by `PrivateSwimlane` for the app ALB and API ALB
(`_create_app_alb`, `_create_api_alb`, `create_alb`); targets are wired for
static web apps, EC2 app instances, and private APIs (see
[[entities/private-swimlane-module]]).

Related: [[syntheses/resources-subsystem]],
[[concepts/capepulumi-base-classes]], [[entities/scoped-swimlane-module]].
