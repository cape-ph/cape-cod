---
type: source
title: "Observation: Pulumi preview found unrelated Cognito provider drift"
tags:
  - pulumi
  - deployment
  - cognito
  - drift
  - issue-379
  - dap
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-pulumi-preview-found-unrelated-cognito-provider-drift
relevance: high
observed_at: 2026-09-23T14:47:31.076Z
source_context: Deployment readiness review for the Decimal serialization fix
---

# ⭐ Observation: Pulumi preview found unrelated Cognito provider drift

Pulumi preview for cape-cod-dev after the Decimal handler fix planned two updates: the intended submit_dap_run Lambda code update and an unrelated GTRI-SSO Cognito identity-provider update removing AWS-populated ActiveEncryptionCertificate, SLORedirectBindingURI, and SSORedirectBindingURI fields. Read-only checks showed live AWS and Pulumi state agree on the provider details, so the IdP action appears to be provider/state normalization drift and must be reviewed before deployment. No deploy was run.

*Relevance: high*
*Context: Deployment readiness review for the Decimal serialization fix*
*Tags: pulumi deployment cognito drift issue-379 dap*

---
*Observed: 2026-09-23T14:47:31.076Z*
