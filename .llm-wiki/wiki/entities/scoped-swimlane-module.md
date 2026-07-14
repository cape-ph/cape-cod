---
type: entity
title: "swimlane base (capeinfra/swimlane.py)"
slug: scoped-swimlane-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["swimlane", "vpc", "networking", "subnets", "base-class"]
---

# swimlane base (`capeinfra/swimlane.py`)

The networking/scaffolding base class that concrete swimlanes extend. A
"swimlane" is a self-contained networked environment (VPC + subnets + routing +
DNS + load balancing + compute scaffolding).

## `SubnetType` (enum)

Enumerates subnet roles. Carries a TODO referencing ISSUE #198 (subnet handling
is slated for rework).

## `ScopedSwimlane(CapeComponentResource)`

Abstract-ish base providing VPC/subnet/NAT/DNS/ALB machinery. Concrete swimlanes
(e.g. [[entities/private-swimlane-module]]) subclass it.

- Constructor: `ScopedSwimlane(basename, *, data_catalog=None, **kwargs)` -
  takes an optional shared `CatalogDatabase` (see [[entities/datalake-module]]).
- Properties: `scope`, `basename`, `vpc_name`, `internet_gateway`.
- VPC/subnets:
  - `create_vpc()` - creates the VPC.
  - `create_subnets()` - creates configured subnets; helpers
      `_check_subnet_configs`, `_resolve_subnet_dependencies`, `_setup_subnet`,
      `_setup_nat_subnet`, `_create_route_list`, `_create_subnet_route_table`
      handle validation, dependency ordering, NAT, and routing. Much of this is
      tagged with TODO ISSUE #198.
  - `get_subnets_by_type(sn_type)` - filter subnets by role.
- DNS/certs:
  - `create_domain_cert()` - domain ACM cert (see [[entities/certs-module]]).
  - `create_hosted_domain(domain_name)`, `create_private_hosted_dns(subnets)`,
      `create_private_domain_alb_record(...)`.
- Load balancing:
  - `create_alb(alb_id, subnets, acmcert)` - creates an `AppLoadBalancer` (see
      [[entities/loadbalancer-module]]).
- Compute scaffolding (delegating to pipeline subsystem):
  - `create_container_images()`, `create_job_definitions()`,
      `create_batch_compute_environments()` (see [[entities/batch-module]],
      [[entities/ecr-module]]),
  - `create_airflow_compute_environment()` (overridden by subclasses; see
      [[entities/airflow-module]]).

Related: [[syntheses/cape-cod-architecture-overview]],
[[concepts/capepulumi-base-classes]], [[entities/private-swimlane-module]].
