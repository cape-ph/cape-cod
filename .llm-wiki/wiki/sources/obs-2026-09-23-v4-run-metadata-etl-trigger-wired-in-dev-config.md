---
type: source
title: "Observation: V4 run metadata ETL trigger wired in dev config"
tags:
  - issue-379
  - bactopia
  - v4
  - metadata
  - etl
  - glue
  - pulumi
  - report
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-v4-run-metadata-etl-trigger-wired-in-dev-config
relevance: high
observed_at: 2026-09-23T18:06:55.975Z
source_context: Wiring metadata sidecar ETL trigger before owner deployment review
---

# ⭐ Observation: V4 run metadata ETL trigger wired in dev config

Wired the v4 run metadata sidecar into the seqauto CAPE ETL contract. Pulumi.cape-cod-dev.yaml now registers bactopia-run-metadata on result-raw prefix pipeline-output/cape-metadata/bactopia-runs with JSON suffix, reusing etl_bactopia_results.py. The ETL recognizes run-manifest.json, parses it through BactopiaOutputContractV1Adapter, and writes crawlable CSV to software_versions/bactopia_run=<run>/software_versions.csv for the existing result_software_versions report joins. Focused tests pass 36; YAML and Ruff/compile checks pass. Pulumi preview shows 5 creates and 3 updates, with known SSO drift accepted; no deploy or commit performed.

*Relevance: high*
*Context: Wiring metadata sidecar ETL trigger before owner deployment review*
*Tags: issue-379 bactopia v4 metadata etl glue pulumi report*

---
*Observed: 2026-09-23T18:06:55.975Z*
