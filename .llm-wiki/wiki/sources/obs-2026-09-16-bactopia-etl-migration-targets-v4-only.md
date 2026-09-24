---
type: source
title: "Observation: Bactopia ETL migration targets v4 only"
tags:
  - bactopia
  - etl
  - v4
  - migration
  - schema
status: observation
created: 2026-09-16
updated: 2026-09-16
slug: obs-2026-09-16-bactopia-etl-migration-targets-v4-only
relevance: high
observed_at: 2026-09-16T17:19:30.803Z
source_context: Reviewing Bactopia v4 output compatibility with the current results ETL
---

# ⭐ Observation: Bactopia ETL migration targets v4 only

The Bactopia results ETL migration will support Bactopia v4.1 only, not a dual v3/v4 parser. The v4 MLST handler should validate the known header, emit a deliberate v4 schema for the semicolon-delimited ALLELES field, and fail clearly on unexpected schema changes. Future Bactopia versions should be supported through explicit versioned adapters or manifests. Findings are recorded in .llm-wiki/wiki/analyses/kraken2-and-bactopia-41-migration-findings.md.

*Relevance: high*
*Context: Reviewing Bactopia v4 output compatibility with the current results ETL*
*Tags: bactopia etl v4 migration schema*

---
*Observed: 2026-09-16T17:19:30.803Z*
