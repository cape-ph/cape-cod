---
type: source
title: "Observation: Always gate code changes behind explicit user approval; wait for option selection before editing"
slug: obs-2026-08-07-always-gate-code-changes-behind-explicit-user-approval-wait-
status: observation
created: 2026-08-07
updated: 2026-08-07
relevance: critical
observed_at: 2026-08-07T15:00:21.286Z
tags: ["workflow", "preference", "approval-gate", "code-changes", "cape-cod", "process"]
source_context: "User correction: gate all code changes behind explicit approval"
---
# 🔴 Observation: Always gate code changes behind explicit user approval; wait for option selection before editing
User workflow preference (cape-cod, applies broadly): ALWAYS gate code changes behind explicit user approval. When presenting implementation options, STOP and wait for the user to select one before making any edits - do not present options and implement in the same turn, even if the choice seems obvious. Investigation, diagnosis, and read-only work can proceed, but any code/config edit needs an explicit go-ahead first. Context: on branch 366 I restated three fix options and then immediately implemented Option A without letting the user choose; the option was correct so nothing was undone, but the user flagged the missing decision gate and asked to always gate code changes with their say-so.
*Relevance: critical*

*Context: User correction: gate all code changes behind explicit approval*

*Tags: workflow preference approval-gate code-changes cape-cod process*
---
*Observed: 2026-08-07T15:00:21.286Z*