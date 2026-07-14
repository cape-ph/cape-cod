---
type: source
title: "Observation: ABAC field intent from cape-cod-db fixtures: code, s3-path identifier, single access_type, no data API"
slug: obs-2026-07-13-abac-field-intent-from-cape-cod-db-fixtures-code-s3-path-ide
status: observation
created: 2026-07-13
updated: 2026-07-13
relevance: high
observed_at: 2026-07-13T18:02:06.466Z
tags: ["abac", "cape-cod-db", "resource-identifier", "access-type", "tributary-code", "attributes", "fixtures"]
source_context: "ABAC Pulumi resource export design - deriving field intent from cape-cod-db fixtures"
---
# ⭐ Observation: ABAC field intent from cape-cod-db fixtures: code, s3-path identifier, single access_type, no data API
cape-cod-db fixtures/test/test_data.sql reveals the schema author's intent for the ABAC fields (better than the prose notes): (1) tributary.code = short stable join key (ENG, DS, OPS, PLAT-ENG), used in every WHERE t.code=...; tributary.name = human display (Engineering). (2) resource.resource_identifier = most-natural canonical per-type id, globally unique: s3:// path for S3 (s3://cape-datalake/eng/raw-uploads/), ARN for EC2 (arn:aws:ec2:...:instance/i-eng001), plain id for application (cape-web-app-prod). So S3 uses the s3 path, NOT the ARN - which also matches what OPA holds at request time. (3) access_type is a single value per resource row (read/write/both/ssh/admin); because resource_identifier is globally unique you cannot have separate read+write rows for the same identifier. raw-uploads/raw-results=write, clean-uploads/clean-results=read, plat deployments=both. (4) attributes JSONB for S3 carries bucket, path_prefix, category (raw_uploads/clean_uploads/raw_results/clean_results/...). NOTE divergence: fixture assumes ONE datalake bucket with per-tributary path prefixes, but real cape-cod infra (capeinfra/datalake/datalake.py Tributary.configure_bucket) provisions a SEPARATE VersionedBucket per bucket-id, so real resource_identifier would be whole-bucket s3://<bucket>/ with category in attributes. Also: cape_cod_db exposes NO data-access API (empty __init__, only SQLModel model classes + database.engine + create_tables); importing cape_cod_db.database calls exit(1) when DB_URL unset, so Pulumi-side code must import only cape_cod_db.models.
*Relevance: high*

*Context: ABAC Pulumi resource export design - deriving field intent from cape-cod-db fixtures*

*Tags: abac cape-cod-db resource-identifier access-type tributary-code attributes fixtures*
---
*Observed: 2026-07-13T18:02:06.466Z*