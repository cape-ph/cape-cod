---
type: source
title: "Observation: ABAC schema-rework handoff written to cape-cod-db (ResourceGrant per-subject model)"
slug: obs-2026-07-13-abac-schema-rework-handoff-written-to-cape-cod-db-resourcegr
status: observation
created: 2026-07-13
updated: 2026-07-13
relevance: critical
observed_at: 2026-07-13T19:17:58.661Z
tags: ["abac", "cape-cod-db", "handoff", "resourcegrant", "schema-rework", "opa", "resource", "tributary"]
source_context: "ABAC cross-repo work - handoff to cape-cod-db schema session"
---
# 🔴 Observation: ABAC schema-rework handoff written to cape-cod-db (ResourceGrant per-subject model)
Created ABAC schema-rework handoff doc at ../cape-cod-db/ABAC_REWORK_HANDOFF.md (sibling repo) to drive a focused cape-cod-db session. Core proposed change: Resource becomes a pure catalog; access moves off the single-access_type row into a new ResourceGrant table (per-subject, per-resource, per-action). ResourceGrant sketch: id PK; exactly one of user_id/tributary_id (CHECK constraint) as subject; resource_id FK ON DELETE CASCADE; access_type (one action per row); granted_by; expires_at; UNIQUE(user_id,tributary_id,resource_id,access_type); indexes on the FKs. Effective access = UNION of (explicit user grant, explicit tributary grant, role-based default from UserTributary.role + Resource.attributes.category) with default-deny and user_status guards; computed in Rego, not stored. Resource.access_type recommended DROP (derive default from category) or keep as nullable default_access. Keeps User/Tributary/UserTributary/UserAttribute as-is. Doc includes: authoritative-sources warning (models.py+migration+fixture truth, notes stale), migration+fixture+notes-refresh plan, the Pulumi export JSON format that feeds Tributary+Resource (catalog only; memberships/grants come from admin/Cognito), the cape-cod-env sync script boundary (out of scope for cape-cod-db), and 7 decisions to confirm (D1 grant cardinality, D2 subject model, D3 access_type drop/keep, D4 ResourceGrant vs AccessGrant name, D5 role/category->action mapping, D6 resource_type "s3", D7 deny-grants out of scope). Workflow: user opens a cape-cod-db session with this doc, implements, reports back final names/constraints so we finalize the cape-cod export module + cape-cod-env sync.
*Relevance: critical*

*Context: ABAC cross-repo work - handoff to cape-cod-db schema session*

*Tags: abac cape-cod-db handoff resourcegrant schema-rework opa resource tributary*
---
*Observed: 2026-07-13T19:17:58.661Z*