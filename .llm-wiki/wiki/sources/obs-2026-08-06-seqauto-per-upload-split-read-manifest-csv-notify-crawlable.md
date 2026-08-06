---
type: source
title: "Observation: seqauto per-upload split-read manifest.csv (notify + crawlable)"
slug: obs-2026-08-06-seqauto-per-upload-split-read-manifest-csv-notify-crawlable
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: high
observed_at: 2026-08-06T16:30:35.309Z
tags: ["seqauto", "notify", "manifest", "datalake", "etl", "pr362"]
source_context: "Extending seqauto notify plumbing with a queryable per-upload split-read manifest"
---
# ⭐ Observation: seqauto per-upload split-read manifest.csv (notify + crawlable)
Augmented the seqauto notify branch (PR #362, commit c9ea7e9) with a per-upload manifest of split reads. etl_seqarchive.py writes one manifest.csv per uploaded archive to manifest/<sink_prefix>/manifest.csv, one row per split read with columns sample_id, source_archive_key, sink_prefix, file_key, file_size. Design decisions: (1) chose a dedicated top-level manifest/ prefix over co-locating under sequencing-reads-split/ so the existing validated split-reads notify rule stays untouched - manifest/ and sequencing-reads-split are disjoint prefixes, and the notify rule model is prefix + suffix-allowlist with no excludes, so co-location would have forced a .gz suffix on the reads rule to avoid a spurious split-reads notification for the manifest. (2) Format is CSV (not JSON) so it is crawler-friendly and queryable in the Glue catalog like meta.csv; manifest/ is deliberately left OUT of the input-clean crawler excludes (which exclude sequencing-reads/** and sequencing-reads-split/**). No crawler infra change - the next crawl picks up the new prefix. (3) Added a split-reads-manifest notify rule (src input-clean, prefix manifest); retention is queue-level (first non-None across notify cfgs) so it is not repeated on the second rule. pulumi preview -s cape-cod-dev: only in-place updates (ETL script object + notifier NOTIFY_RULES env gaining rule [1]); 3 to update, 472 unchanged, no creates/replaces/deletes. Per-row duplication of archive/sample columns accepted for the demo. There was no pre-existing manifest/manifest.json concept; the earlier per-upload metadata artifact is meta/<sink_prefix>/meta.csv.
*Relevance: high*

*Context: Extending seqauto notify plumbing with a queryable per-upload split-read manifest*

*Tags: seqauto notify manifest datalake etl pr362*
---
*Observed: 2026-08-06T16:30:35.309Z*