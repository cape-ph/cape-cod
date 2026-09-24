---
type: source
title: Publisher edge-case coverage before owner review
status: insight
category: testing
created: 2026-09-23
updated: 2026-09-23
slug: publisher-edge-case-coverage-before-owner-review
---

# Publisher edge-case coverage before owner review

The pipeline asset publisher now has focused unit coverage in `tests/test_pipeline_assets.py` for checksum-list parsing, archive path traversal rejection, checksum mismatch, inventory mismatch, immutable S3 prefix rejection, manifest-last publication ordering, and scratch-directory cleanup. The focused suite passes 32 tests with Ruff, Python compilation, and `git diff --check`. The implementation remains uncommitted pending owner review. Future publisher boundary work is tracked in [[sources/obs-2026-09-23-pipeline-asset-adapter-refactor-deferred-with-tracking-issue]]. The eventual move to `cape-cod-env` needs a separate tracking issue before the PR.

*Category: testing*

---
*Captured: 2026-09-23*

## Related

_Add links to related pages._
