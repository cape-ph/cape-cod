---
type: source
title: "Observation: Filed cape-cod resource-export implementation plan + export architecture/decisions"
slug: obs-2026-07-13-filed-cape-cod-resource-export-implementation-plan-export-ar
status: observation
created: 2026-07-13
updated: 2026-07-13
relevance: critical
observed_at: 2026-07-13T20:21:53.728Z
tags: ["abac", "resource-export", "pulumi", "cape-cod", "plan", "export-format", "datalake", "open-questions"]
source_context: "Building the cape-cod resource-export implementation plan"
---
# 🔴 Observation: Filed cape-cod resource-export implementation plan + export architecture/decisions
Filed the cape-cod resource-export implementation plan at .llm-wiki/wiki/syntheses/abac-resource-export-implementation-plan.md and updated syntheses/abac-opa-cross-repo.md to the post-rework schema. Key engineering facts mapped in cape-cod: program assembly is capeinfra/__init__.py (module-level data_lakehouse = DatalakeHouse(...)) consumed by __main__.py; there is NO pulumi.export yet. DatalakeHouse.tributaries is a list of Tributary; each Tributary.buckets is dict[str,VersionedBucket] keyed by bucket_id (input-raw/input-clean/result-raw/result-clean). VersionedBucket.bucket is the aws.s3.Bucket; physical name = vb.bucket.bucket (Output), ARN = vb.bucket.arn (Output). Bucket config name: is empty so AWS auto-names buckets (physical name is Output, only known after up, and volatile on bucket replacement). Config wrapper is CapeConfig.get(*keys, default); trib config is passed as config=trib_config so display_name/description can be added as optional tributary config keys and captured in Tributary.__init__. Tests use @pulumi.runtime.test + Output.all(...).apply(check) with PulumiMock in tests/conftest.py (loads Pulumi.cape-cod-dev.yaml). Three tributaries: hai, genomics, seqauto, 4 standard buckets each. PLAN DECISIONS: export populates Tributary+Resource catalog only (no access_type, no grants); resource_identifier = s3://<physical-bucket>/; attributes carry bucket/arn/category/bucket_role/tributary_code/environment/managed_by; category map input-raw->raw_uploads,input-clean->clean_uploads,result-raw->raw_results,result-clean->clean_results. Architecture: pure builders (_category_for_bucket_id,_resource_record) + build_resource_export(dlh,stack)->Output[dict] in new capeinfra/authz/export.py; pulumi.export("abac_resource_export",...) in __main__.py; local file via `pulumi stack output abac_resource_export --json > cape-cod-export.json` (no in-program file writes). KEY OPEN QUESTION O1 (reverses earlier lean): recommend cape-cod does NOT depend on cape-cod-db - emit plain dicts, keep ORM stack out of the IaC venv, and let cape-cod-env validate the JSON against the models (it depends on cape-cod-db anyway). Also O2 stable bucket names vs logical-identity reconcile; carry tributary_code+bucket_role in attributes so env reconcile survives physical-name churn.
*Relevance: critical*

*Context: Building the cape-cod resource-export implementation plan*

*Tags: abac resource-export pulumi cape-cod plan export-format datalake open-questions*
---
*Observed: 2026-07-13T20:21:53.728Z*