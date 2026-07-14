---
type: source
title: "Observation: Verified: cape-cod-db ABAC rework complete (Resource pure catalog, ResourceGrant added, migration 010c0bff0b83)"
slug: obs-2026-07-13-verified-cape-cod-db-abac-rework-complete-resource-pure-cata
status: observation
created: 2026-07-13
updated: 2026-07-13
relevance: high
observed_at: 2026-07-13T20:21:53.718Z
tags: ["abac", "cape-cod-db", "resourcegrant", "migration", "schema", "verified", "rework"]
source_context: "Investigating completed cape-cod-db ABAC rework as source of truth"
---
# ⭐ Observation: Verified: cape-cod-db ABAC rework complete (Resource pure catalog, ResourceGrant added, migration 010c0bff0b83)
Verified the cape-cod-db ABAC schema rework is COMPLETE on the local abac_schema_rework branch (unmerged, unreleased). Migration 010c0bff0b83 ("abac per-subject resource grants", down_revision 6919c61ea401): DROPS resource.access_type and CREATES table resourcegrant. Final schema in cape_cod_db/models.py: Resource is now a pure catalog (resource_type indexed, resource_identifier unique+indexed, display_name, tributary_id nullable FK, attributes JSONB with GIN jsonb_path_ops index) - NO access_type. New ResourceGrant(CapeModel): id PK; user_id/tributary_id nullable FKs ON DELETE CASCADE; CHECK ck_resourcegrant_exactly_one_subject "(user_id IS NOT NULL) <> (tributary_id IS NOT NULL)"; resource_id FK ON DELETE CASCADE nullable=False; access_type (one action per row); granted_by FK user (no cascade); expires_at; UNIQUE uq_resourcegrant_subject_resource_access on (user_id,tributary_id,resource_id,access_type) postgresql_nulls_not_distinct=True; indexes on the 3 FKs. Tributary/User/UserTributary/UserAttribute unchanged. env.py imports ResourceGrant for autogenerate. Fixtures updated (test_data.sql now inserts resourcegrant rows: user grant, tributary grant, expiring grant). cape-cod-db retired notes/ for its own .llm-wiki (concepts/abac-authorization-design, entities/database-schema). IMPORTANT gaps: package version still 0.3.0 and CHANGELOG not bumped for the rework -> cape-cod-env cannot pin the new schema until cape-cod-db cuts a release (>=0.4.0). Minor stale doc: cape-cod-db entities/test-fixtures.md still says resources have access_type values write/read/both/ssh/admin (those now live in resourcegrant).
*Relevance: high*

*Context: Investigating completed cape-cod-db ABAC rework as source of truth*

*Tags: abac cape-cod-db resourcegrant migration schema verified rework*
---
*Observed: 2026-07-13T20:21:53.718Z*