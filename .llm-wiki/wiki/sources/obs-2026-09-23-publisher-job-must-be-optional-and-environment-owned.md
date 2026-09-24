---
type: source
title: "Observation: Publisher job must be optional and environment-owned"
tags:
  - pipeline-assets
  - publisher
  - aws-batch
  - cape-cod-env
  - cost
  - optional
  - deployment
status: observation
created: 2026-09-23
updated: 2026-09-23
slug: obs-2026-09-23-publisher-job-must-be-optional-and-environment-owned
relevance: high
observed_at: 2026-09-23T11:07:53.466Z
source_context: Publisher execution and cost design discussion
---

# ⭐ Observation: Publisher job must be optional and environment-owned

The pipeline asset publisher should not be a dependency of cape-cod Pulumi deployment or any current pipeline. A future `cape-cod-env` deployment flow can invoke the standalone publisher and fail that environment asset step clearly if publication is missing, while cape-cod only exposes the meta-assets bucket and runtime export. AWS Batch is a normal target for the one-shot containerized publisher because it provides IAM roles, logs, retries, and ephemeral compute; use a role-based job rather than developer session credentials. A rough us-east-2 one-hour m5.large estimate is about $0.096 EC2, a few mills of temporary gp3 scratch, small same/cross-region transfer and S3 request costs, plus about $0.20/month for an 8.6 GB S3 Standard database. Batch itself has no separate fee. A dedicated queue with min capacity zero avoids idle cost; an existing workflow host may make the marginal compute cost zero but competes for capacity. The current local publisher attempt failed after download because its session token expired, reinforcing that it should eventually run in AWS or another role-based deployment environment.

*Relevance: high*
*Context: Publisher execution and cost design discussion*
*Tags: pipeline-assets publisher aws-batch cape-cod-env cost optional deployment*

---
*Observed: 2026-09-23T11:07:53.466Z*
