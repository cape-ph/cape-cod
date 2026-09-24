---
type: source
title: "Observation: Normal DAP invocation exposed Decimal override serialization bug"
tags:
  - issue-379
  - dap
  - handler
  - decimal
  - process
  - overrides
  - taxprofiler
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-normal-dap-invocation-exposed-decimal-override-serialization
relevance: high
observed_at: 2026-09-23T11:51:55.403Z
source_context: Normal DAP path test against published Standard-8 asset
---

# ⭐ Observation: Normal DAP invocation exposed Decimal override serialization bug

The normal DAP handler invocation was attempted with the published Standard-8 database sheet and failed before Batch submission. The deployed Lambda deserialized DynamoDB numeric process override values as `Decimal`, then `json.dumps(process_overrides)` raised `TypeError: Object of type Decimal is not JSON serializable`. The local handler now has recursive Decimal-to-int/float normalization and a focused test uses `Decimal("2")`; 26 focused tests pass. The fix is uncommitted and requires a user-approved Pulumi deployment before the normal DAP path can be retried. No parent job was submitted by the failed invocation.

*Relevance: high*
*Context: Normal DAP path test against published Standard-8 asset*
*Tags: issue-379 dap handler decimal process overrides taxprofiler*

---
*Observed: 2026-09-23T11:51:55.403Z*
