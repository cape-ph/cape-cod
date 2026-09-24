---
type: source
title: "Observation: DAP handler reuses capepy Decimal serializer"
tags:
  - issue-379
  - dap
  - decimal
  - capepy
  - batch
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-dap-handler-reuses-capepy-decimal-serializer
relevance: high
observed_at: 2026-09-23T12:08:43.772Z
source_context: Replacing the local Decimal normalization before user review
---

# ⭐ Observation: DAP handler reuses capepy Decimal serializer

Updated assets/api/capi/handlers/submit_dap_run.py to pass capepy.aws.utils.json_serialize_the_unserializable as json.dumps(default=...) for DynamoDB-backed process overrides. This removes the duplicate recursive Decimal converter while preserving nested override serialization. Focused tests, Ruff, bytecode compilation, and git diff checks pass; no commit or deployment was performed.

*Relevance: high*
*Context: Replacing the local Decimal normalization before user review*
*Tags: issue-379 dap decimal capepy batch*

---
*Observed: 2026-09-23T12:08:43.772Z*
