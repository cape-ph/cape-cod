---
type: entity
title: "assets: instance user-data (assets/instance/user-data/)"
slug: assets-instance-user-data
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["ec2", "user-data", "bootstrap", "jinja", "assets"]
---

# assets: instance user-data (`assets/instance/user-data/templates/`)

Jinja2-templated EC2 bootstrap (user-data) scripts, rendered at deploy time and
attached to the application EC2 instances created by
`PrivateSwimlane.create_application_instances` (see
[[entities/private-swimlane-module]]). Rendered via [[entities/util-modules]]
Jinja helpers.

## Per-file

- `cape-frontend.j2` - writes `/opt/cape-frontend/env` with `NODE_ENV`, `HOST`,
  and Cognito settings (`PUBLIC_COGNITO_AUTHORITY`, `PUBLIC_COGNITO_CLIENT_ID`,
  `PUBLIC_COGNITO_REDIRECT_URI` built from `{{ cognito_pool_endpoint }}`,
  `{{ cognito_client_id }}`, `{{ domain }}`), then restarts
  `cape-frontend.service`. This is the CAPE web UI front end.
- `jupyterhub.j2` - bootstrap for the JupyterHub instance (accessed via the
  jupyterhub route; see `extra-doc/README.using-cape.md`).
- `opa.j2` - bootstrap for an OPA (Open Policy Agent) instance. Writes
  `/etc/opa/config/opa-config.yaml` configuring OPA to pull a versioned `authz`
  policy bundle from a GitHub releases URL with polling
  (`min_delay_seconds`/`max_delay_seconds`); notes an optional S3-backed bundle
  service for the future. This is the policy-decision point for CAPE's ABAC; see
  [[syntheses/abac-opa-cross-repo]].

Template variables (Cognito endpoint/client id, domain, etc.) are supplied by
the swimlane from `CapePrincipals` (Cognito) outputs and config (see
[[entities/capemeta-module]], [[concepts/pulumi-config-structure]]).

Related: [[syntheses/assets-subsystem]], [[entities/private-swimlane-module]],
[[syntheses/abac-opa-cross-repo]].
