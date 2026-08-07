---
type: source
title: "Observation: Deploy hazard: deploying a branch cut from main can revert live work deployed from another unmerged branch (shared dev stack)"
slug: obs-2026-08-07-deploy-hazard-deploying-a-branch-cut-from-main-can-revert-li
status: observation
created: 2026-08-07
updated: 2026-08-07
relevance: critical
observed_at: 2026-08-07T15:03:50.482Z
tags: ["cape-cod", "pulumi", "deploy", "shared-stack", "branch-ordering", "rebase", "issue-366", "branch-363", "process", "hazard"]
source_context: "Realizing branch 366 deploy would revert deployed-but-unmerged branch 363 report work"
---
# 🔴 Observation: Deploy hazard: deploying a branch cut from main can revert live work deployed from another unmerged branch (shared dev stack)
Deploy-ordering hazard on cape-cod (shared single dev stack, cape-cod-dev): pulumi up deploys whatever the checked-out branch's tree/config declares, so deploying a branch cut from main can REVERT live work that was deployed from a different unmerged branch. Concrete case: branch 366-fixreports (weasyprint layer dedup) was cut from main and does NOT contain yesterday's report-gen/caerbannog RABiTS report work that is already deployed to dev from branch 363. Deploying 366 in isolation would whack that deployed-but-unmerged 363 work. Remedy: do NOT deploy 366 alone. First land 363's report-gen work in main, then rebase 366 onto updated main (git rebase origin/main) so its tree includes everything, then pulumi preview --diff -s cape-cod-dev (expect only the kotify-cpu tag bump to weasyprint-69.0 + report-gen layer rebuild, nothing destructive), then user deploys. General rule: before any dev deploy, make sure the branch's tree is a superset of what is currently deployed, or you will roll back other people's live changes on the shared stack.
*Relevance: critical*

*Context: Realizing branch 366 deploy would revert deployed-but-unmerged branch 363 report work*

*Tags: cape-cod pulumi deploy shared-stack branch-ordering rebase issue-366 branch-363 process hazard*
---
*Observed: 2026-08-07T15:03:50.482Z*