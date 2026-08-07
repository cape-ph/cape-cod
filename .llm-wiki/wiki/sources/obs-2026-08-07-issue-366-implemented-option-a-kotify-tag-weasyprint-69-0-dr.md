---
type: source
title: "Observation: Issue #366 implemented (Option A): kotify tag -> weasyprint-69.0, dropped report-gen weasyprint; pending preview/deploy/PDF validation"
slug: obs-2026-08-07-issue-366-implemented-option-a-kotify-tag-weasyprint-69-0-dr
status: observation
created: 2026-08-07
updated: 2026-08-07
relevance: high
observed_at: 2026-08-07T14:58:38.074Z
tags: ["cape-cod", "reports", "weasyprint", "kotify", "lambda-layers", "issue-366", "pdf", "pulumi", "dedup", "branch-366"]
source_context: "Implementing issue #366 fix (Option A: bump kotify to 69.0 + drop report-gen weasyprint)"
---
# ⭐ Observation: Issue #366 implemented (Option A): kotify tag -> weasyprint-69.0, dropped report-gen weasyprint; pending preview/deploy/PDF validation
Implemented issue #366 (weasyprint layer dedup) on branch 366-fixreports-dedup-and-upgrade-weasyprint-lambda-layers-to-resolve-pdf-parser-collision, using Option A (bump + dedup). Two edits:
1. Pulumi.cape-cod-dev.yaml: kotify-cpu gh-release layer tag weasyprint-68.0 -> weasyprint-69.0 (asset unchanged: weasyprint-layer-python3.13-x86_64.zip). Bundle becomes weasyprint 69.0 + tinyhtml5 2.1.0 (matched pair; clears CVE-2026-49452 and CVE-2025-68616; eliminates the override_encoding TypeError at the source).
2. assets/lambda-layers/report-gen/requirements.txt: removed weasyprint==66.0, kept Jinja2==3.1.6. kotify is now the single Python weasyprint source (kotify does not bundle Jinja2, so it stays in report-gen).
Diff is exactly those two lines. YAML still parses (python yaml.safe_load OK). The 42 line-length lint findings on Pulumi.cape-cod-dev.yaml are all pre-existing long comment/path lines, none on the changed line - left untouched (out of scope). Options B (align both layers to 69.0, keeps two redundant stacks) and C (native-libs-only repackage to also patch Pillow) were rejected/deferred; Pillow mitigation is explicitly out of scope for this branch and relies on non-reachability (no raster images in the template).
NOT yet committed (needs approval) and NOT deployed. Remaining validation per CAPE deploy prep: run pulumi preview --diff -s cape-cod-dev (expect kotify-cpu layer version rebuild from the new gh-release tag + report-gen layer rebuild from the changed requirements; no destructive ops expected), then user deploys, then confirm a PDF render for sample_id abcdefghij returns 200 with a valid PDF (previously 500 with override_encoding error).
*Relevance: high*

*Context: Implementing issue #366 fix (Option A: bump kotify to 69.0 + drop report-gen weasyprint)*

*Tags: cape-cod reports weasyprint kotify lambda-layers issue-366 pdf pulumi dedup branch-366*
---
*Observed: 2026-08-07T14:58:38.074Z*