---
type: source
title: "Observation: Verified: pulumi preview confirms abac_resource_export output (12 records, real bucket names, zero churn)"
slug: obs-2026-07-14-verified-pulumi-preview-confirms-abac-resource-export-output
status: observation
created: 2026-07-14
updated: 2026-07-14
relevance: high
observed_at: 2026-07-14T18:36:48.588Z
tags: ["abac", "resource-export", "pulumi", "preview", "verified", "cape-cod", "datalake"]
source_context: "Verifying cape-cod ABAC resource export via pulumi preview"
---
# ⭐ Observation: Verified: pulumi preview confirms abac_resource_export output (12 records, real bucket names, zero churn)
pulumi preview -s cape-cod-dev succeeded (PREVIEW_EXIT=0) after the network/S3-state-backend issue was resolved, fully verifying the ABAC resource export end-to-end. The abac_resource_export stack output rendered with real AWS-resolved bucket names (e.g. s3://ccd-dlh-t-seqauto-input-clean-vbkt-s3-b1f75c7/), ARNs, and all attributes (bucket, arn, category, bucket_role, tributary_code, environment=cape-cod-dev, managed_by=cape-cod-pulumi), display_name (e.g. "seqauto Raw Uploads"), resource_type "s3". Counts: exactly 12 resource records (3 tributaries hai/genomics/seqauto x 4 buckets), categories split 3/3/3/3 across raw_uploads/clean_uploads/raw_results/clean_results, version "1.0", pulumi_stack "cape-cod-dev". CRITICAL: my changes (Tributary.__init__ attribute capture + pulumi.export) produce ZERO resource churn - the only add is the new stack output. The preview's unrelated pre-existing drift was: cognito IdentityProvider (providerDetails), cognito demo User (temporaryPassword), report-gen lambda LayerVersion replace (changed s3ObjectVersion) cascading to its BucketObjectv2 assets, batch JobDefinition, capi getcannedreport Function layers, and nextflow-jobdef IAM policy - none touch tributaries/authz/datalake buckets. Summary line: "8 to update, +-1 to replace, 460 unchanged". The Output.all(...).apply(...) plumbing in build_resource_export is now confirmed to resolve correctly against real deployed buckets, not just unit tests.
*Relevance: high*

*Context: Verifying cape-cod ABAC resource export via pulumi preview*

*Tags: abac resource-export pulumi preview verified cape-cod datalake*
---
*Observed: 2026-07-14T18:36:48.588Z*