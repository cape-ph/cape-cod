---
type: source
title: "Observation: Asset publisher must remain cape-cod-env portable"
tags:
  - pipeline-assets
  - cape-cod-env
  - publisher
  - migration
  - credentials
  - s3
status: observation
created: 2026-09-22
updated: 2026-09-22
slug: obs-2026-09-22-asset-publisher-must-remain-cape-cod-env-portable
relevance: critical
observed_at: 2026-09-22T20:37:00.635Z
source_context: End-of-day handoff after failed Standard-8 publication
---

# 🔴 Observation: Asset publisher must remain cape-cod-env portable

The pipeline asset publisher must be designed for eventual ownership by `cape-cod-env`, not as a Pulumi-specific implementation. Keep it as a standalone Python package/CLI with no Pulumi imports, driven by portable per-asset manifests and immutable S3 prefixes. `cape-cod` should provide only the shared meta-assets bucket, permissions/lifecycle, and `cape_pipeline_runtime_export`; `cape-cod-env` should eventually invoke the same publisher from its Ansible/deployment flow. The Standard-8 publication attempt downloaded and validated the 5.95 GB archive locally, then failed before the first S3 upload because the temporary AWS session token expired. Temporary scratch was cleaned and the destination prefix is empty, so no resume is possible without re-download. Do not add a publisher improvement that depends on Pulumi or local developer scratch. The next robust implementation should run in an AWS-hosted job with role-based credentials or use an S3 staging flow, while preserving the same manifest schema and object layout for the repository migration.

*Relevance: critical*
*Context: End-of-day handoff after failed Standard-8 publication*
*Tags: pipeline-assets cape-cod-env publisher migration credentials s3*

---
*Observed: 2026-09-22T20:37:00.635Z*
