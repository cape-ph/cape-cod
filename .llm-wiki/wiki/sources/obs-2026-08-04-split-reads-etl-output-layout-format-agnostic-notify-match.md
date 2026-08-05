---
type: source
title: "Observation: Split-reads ETL output layout + format-agnostic notify match"
slug: obs-2026-08-04-split-reads-etl-output-layout-format-agnostic-notify-match
status: observation
created: 2026-08-04
updated: 2026-08-04
relevance: high
observed_at: 2026-08-04T19:07:20.934Z
tags: ["seqauto", "etl", "datalake", "notifications", "crawler"]
source_context: "Grill-me on the tributary notification plumbing design (seqauto pilot)"
---
# ⭐ Observation: Split-reads ETL output layout + format-agnostic notify match
Grill outcome for the seqauto notification work. The updated seqreadarch ETL (assets/etl/etl_seqarchive.py) will write the individual (un-concatenated) per-read files to input-clean under a NEW dedicated TOP-LEVEL prefix `sequencing-reads-split/<sink_prefix>/<name>.<ext>`, reusing the existing Hive-style partition path (sample_id=.../year=.../.../second=...). The existing concatenated output stays put at `sequencing-reads/<sink_prefix>/sequencing-reads.gz` (do NOT move it - it is referenced by the cataloged meta.csv `sequencing_reads` column). One crawler-exclude line `sequencing-reads-split/**` is added to the input-clean crawler (which already excludes `sequencing-reads/**`).

Decision rationale: the individual files may be `.fastq` OR `.gz` depending on instrument, so a suffix-based notify match is unreliable (gz would collide with the concat). Instead the notify rule matches by the dedicated prefix `sequencing-reads-split` alone (format-agnostic), reusing the notifier's existing leading-prefix ancestor-walk (topmost ancestor equals the prefix). A dedicated TOP-LEVEL prefix was chosen over nesting under sequencing-reads specifically so a simple leading-prefix match works without a new glob/segment matcher; the cost is the one extra crawler-exclude line. Default output format is gzip per file (storage-sane, matches the concat rationale); final format is consumer-driven and can be converted at VM-copy time without touching the notify wiring. input-clean is NOT an ETL source in seqauto, so writing here cannot re-trigger an ETL (no loop).
*Relevance: high*

*Context: Grill-me on the tributary notification plumbing design (seqauto pilot)*

*Tags: seqauto etl datalake notifications crawler*
---
*Observed: 2026-08-04T19:07:20.934Z*