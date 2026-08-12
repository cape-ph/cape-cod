---
type: source
title: "Observation: Caerbannog consumer formats are confidential: ask a dev, keep out of the wiki"
slug: obs-2026-08-06-caerbannog-consumer-formats-are-confidential-ask-a-dev-keep-
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: critical
observed_at: 2026-08-06T18:43:43.506Z
tags: ["cape-cod", "caerbannog", "seqauto", "etl", "confidential", "third-party", "formats", "branch-363", "policy"]
source_context: "Branch 363 caerbannog ETL - handling confidential consumer formats"
---
# 🔴 Observation: Caerbannog consumer formats are confidential: ask a dev, keep out of the wiki
The caerbannog consumer's internal output formats (aggregate CSV columns, and the stoplight / cluster-estimates JSON schemas and example documents) are third-party and NOT under our control. They are considered confidential and must NOT be recorded in this open-source wiki - no real column names, field names, types, or example documents in any wiki page. When working the branch 363 caerbannog ETL (assets/etl/etl_caerbannog_results.py) or the follow-on report changes and you need the actual formats, ASK a dev for them rather than looking for them in the wiki: both devs have the formats available on hand. The code itself necessarily encodes the processed columns/fields; that exposure is accepted and out of scope here - the rule is specifically about not documenting the formats in wiki prose.
*Relevance: critical*

*Context: Branch 363 caerbannog ETL - handling confidential consumer formats*

*Tags: cape-cod caerbannog seqauto etl confidential third-party formats branch-363 policy*
---
*Observed: 2026-08-06T18:43:43.506Z*