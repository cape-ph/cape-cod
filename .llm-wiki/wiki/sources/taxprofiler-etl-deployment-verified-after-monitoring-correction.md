---
type: source
title: Taxprofiler ETL deployment verified after monitoring correction
status: insight
category: operations
created: 2026-09-25
updated: 2026-09-25
slug: taxprofiler-etl-deployment-verified-after-monitoring-correction
---

# Taxprofiler ETL deployment verified after monitoring correction

Corrected the earlier status statement. AWS inspection shows the Glue script object `s3://ccd-meta-assets-vbkt-s3-8b7134e/glue/etl/etl_taxprofiler_results.py` was updated at 2026-09-25T18:22:15Z, and its SHA-256 matches the local ETL layout fix exactly (`758f952846dbec9ee02e373ca4dc591a30469f89b904ca133a1207e1af639c9b`). The deployed script strips an optional `output/` segment and recognizes the current `kraken2`, `multiqc`, and `pipeline_info` paths. The background monitor also accepts both layouts. No new raw run is currently present beyond the existing baseline, so there is no pipeline transition to report yet.

*Category: operations*

---
*Captured: 2026-09-25*

## Related

_Add links to related pages._
