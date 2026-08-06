---
type: source
title: "seqarchive ETL: Phase 1 split-reads output implemented (uncommitted)"
slug: seqarchive-split-reads-phase1-implemented
status: insight
created: 2026-08-04
updated: 2026-08-04
category: architecture
---
# seqarchive ETL: Phase 1 split-reads output implemented (uncommitted)
Phase 1 of the seqauto split-reads work is implemented on branch `361-update-seqauto-tributary-...`, verified, and awaiting the user's deploy/test before commit.

**Changes (both uncommitted in the working tree):**
- `assets/etl/etl_seqarchive.py`: inside the existing `sequencing/` member loop, after the concat write, each member is ALSO written on its own to `sequencing-reads-split/<sink_prefix>/<basename>`, reusing the already-computed `bytes_for_concat`. fasta/fastq members are gzipped (name gets `.gz`); already-gzipped members pass through unchanged. One consistent gzip format. Existing concat output (`sequencing-reads/<sink_prefix>/sequencing-reads.gz`) and `meta/<sink_prefix>/meta.csv` are untouched. Top module comment updated to mention the split output.
- `Pulumi.cape-cod-dev.yaml`: seqauto `input-clean` crawler `excludes` now includes `sequencing-reads-split/**` (a pi-lens autofix reflowed the flow list to multi-line; parses identically).

**Verification (agent-side):** `python -m py_compile` on the ETL script passes; `yaml.safe_load` on the dev config passes; full pytest = 48 passed. The 2 failures (`test_datalake::test_catalog`, `test_capemeta::test_asset_bucket`) are pre-existing AWS `InvalidToken` env failures, unrelated (see [[sources/obs-2026-08-04-fixer-subagent-401-blocked-this-session-test-catalog-test-as]]).

**Status:** parked at the Phase 1 USER TEST GATE. Commit (planned `feat(seqauto): write split per-read files to input-clean`) happens only after the user deploys and confirms. See design in [[sources/obs-2026-08-04-split-reads-etl-output-layout-format-agnostic-notify-match]].
*Category: architecture*
---
*Captured: 2026-08-04*
## Related
_Add links to related pages._