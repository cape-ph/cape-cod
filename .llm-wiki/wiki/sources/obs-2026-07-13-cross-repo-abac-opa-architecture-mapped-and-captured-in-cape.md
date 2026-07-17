---
type: source
title: "Observation: Cross-repo ABAC/OPA architecture mapped and captured in cape-cod wiki"
slug: obs-2026-07-13-cross-repo-abac-opa-architecture-mapped-and-captured-in-cape
status: observation
created: 2026-07-13
updated: 2026-07-13
relevance: high
observed_at: 2026-07-13T17:33:20.093Z
tags: ["abac", "opa", "rds", "cape-cod-db", "cape-cod-env", "authorization", "cross-repo"]
source_context: "Hardening cape-cod wiki for ABAC/OPA + RDS cross-repo work"
---
# ⭐ Observation: Cross-repo ABAC/OPA architecture mapped and captured in cape-cod wiki
Mapped the ABAC/OPA integration across three repos and captured it as syntheses/abac-opa-cross-repo.md in the cape-cod wiki (linked from database-module, private-swimlane-module, assets-instance-user-data, and cross-repo overview). Key flow: cape-cod's PrivateSwimlane.create_env_rds_instance() builds an EMPTY Postgres RDS (db_name=cape_env_db, user=postgres, port 5432, manage_master_user_password=True -> AWS Secrets Manager) from cape-cod:swimlanes.private.env-db-rds. cape-cod-env's cape-cod-env.yaml imports cape_env_db.yaml, which fetches the master password from Secrets Manager (<secret>.password via amazon.aws.aws_secret), builds postgresql://user:pass@host/db, finds the installed cape_cod_db package alembic.ini, and runs `alembic upgrade head`. cape-cod-db is the canonical schema (SQLModel + Alembic), models: User, Tributary, UserTributary (M2M role membership = core ABAC attribute), Resource (generic, JSONB attributes + GIN index), UserAttribute; current migration head 6919c61ea401. OPA runs on an EC2 instance whose user-data assets/instance/user-data/templates/opa.j2 already pulls a versioned authz bundle from a GitHub releases URL with polling. CRITICAL coupling: cape-cod-env must keep cape-cod-db up to date in requirements.txt or `head` silently no-ops. NOT YET BUILT: no pulumi.export of resource metadata in cape-cod, no Ansible resource-sync script in cape-cod-env, no OPA bundle generator (Postgres->JSON->bundle), no in-repo Rego policies, no OPA-gating in capi handlers. Authoritative design: cape-cod-db/notes/06-authorization-design.md.
*Relevance: high*

*Context: Hardening cape-cod wiki for ABAC/OPA + RDS cross-repo work*

*Tags: abac opa rds cape-cod-db cape-cod-env authorization cross-repo*
---
*Observed: 2026-07-13T17:33:20.093Z*