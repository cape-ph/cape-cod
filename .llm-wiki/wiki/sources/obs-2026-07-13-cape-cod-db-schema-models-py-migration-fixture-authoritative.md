---
type: source
title: "Observation: cape-cod-db schema: models.py + migration + fixture authoritative; notes/01 stale"
slug: obs-2026-07-13-cape-cod-db-schema-models-py-migration-fixture-authoritative
status: observation
created: 2026-07-13
updated: 2026-07-13
relevance: high
observed_at: 2026-07-13T18:02:06.457Z
tags: ["abac", "cape-cod-db", "schema", "stale-notes", "authoritative", "resource", "tributary"]
source_context: "ABAC Pulumi resource export design - exploring cape-cod-db schema authority"
---
# ⭐ Observation: cape-cod-db schema: models.py + migration + fixture authoritative; notes/01 stale
cape-cod-db describes its own schema in three places that disagree. Authoritative = cape_cod_db/models.py + Alembic migration 6919c61ea401 + fixtures/test/test_data.sql (these agree). STALE = notes/01-models.md, which documents Resource.access_pattern + Resource.metadata, omits Tributary.code/parent_id/attributes, omits UserTributary.role, gives UserTributary an id PK, and claims Resource uniqueness is (tributary_id, resource_type, resource_identifier, access_pattern). Real code: Resource uses access_type + attributes (JSONB, GIN), resource_identifier is UNIQUE on its own, display_name required; Tributary has code (unique) + parent_id (self-FK) + attributes; UserTributary has composite PK (user_id, tributary_id) + role. notes/00 also still says version 0.2.0 while pyproject/CHANGELOG are 0.3.0 (the release that added ABAC tables). The CONTEXT.md handed over by a prior agent inherited the stale access_pattern/metadata naming from notes/01. Conclusion: build ABAC export/sync against models.py + migration + fixture, not the notes or CONTEXT.md.
*Relevance: high*

*Context: ABAC Pulumi resource export design - exploring cape-cod-db schema authority*

*Tags: abac cape-cod-db schema stale-notes authoritative resource tributary*
---
*Observed: 2026-07-13T18:02:06.457Z*