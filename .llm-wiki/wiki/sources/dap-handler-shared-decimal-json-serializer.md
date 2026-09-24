---
type: source
title: Shared Decimal JSON serializer for DAP overrides
status: insight
category: bugfix
created: 2026-09-23
updated: 2026-09-23
slug: dap-handler-shared-decimal-json-serializer
---

# Shared Decimal JSON serializer for DAP overrides

The normal DAP handler receives numeric process override values from DynamoDB as `Decimal` instances. In `assets/api/capi/handlers/submit_dap_run.py`, serialize `process_overrides` with `json.dumps(..., default=json_serialize_the_unserializable)` from `capepy.aws.utils`, matching the existing GET handlers. This handles nested Decimal values without maintaining a duplicate recursive converter. The focused contract test uses `Decimal("2")` and confirms the generated Batch environment JSON. The fix remains local and uncommitted pending user approval. Related finding: [[sources/obs-2026-09-23-normal-dap-invocation-exposed-decimal-override-serialization]].

*Category: bugfix*

---
*Captured: 2026-09-23*

## Related

_Add links to related pages._
