---
type: source
title: "Observation: Taxprofiler monitor restored after AWS credential refresh"
tags:
  - taxprofiler
  - monitor
  - aws
  - credentials
  - operations
status: observation
created: 2026-09-25
updated: 2026-09-25
slug: obs-2026-09-25-taxprofiler-monitor-restored-after-aws-credential-refresh
relevance: medium
observed_at: 2026-09-25T20:09:51.034Z
source_context: Restoring the long-running taxprofiler pipeline monitor
---

# 🔍 Observation: Taxprofiler monitor restored after AWS credential refresh

AWS STS authentication is valid again for account 767397883306 in us-east-2. Replaced the monitor process after repeated ExpiredToken failures: bg-10 and bg-11 are stopped, and bg-12 is running with a clean startup and no immediate AWS error. It retains the baseline of one existing taxprofiler raw run and is waiting for a new run.

*Relevance: medium*
*Context: Restoring the long-running taxprofiler pipeline monitor*
*Tags: taxprofiler monitor aws credentials operations*

---
*Observed: 2026-09-25T20:09:51.034Z*
