---
type: source
title: Live taxprofiler Kraken2 validation
status: insight
category: validation
created: 2026-09-25
updated: 2026-09-25
slug: live-taxprofiler-kraken2-validation
---

# Live taxprofiler Kraken2 validation

The deployed taxprofiler Kraken2 path is validated end to end in the dev AWS account. The Glue ETL wrote partitioned clean data, the seqauto result-clean crawler succeeded, and Athena exposed the primary `result_kraken2_taxa` and `result_kraken2_summary` tables plus ten nonempty auxiliary taxprofiler tables. The deployed data Lambda returned the expected summary and taxonomy tree data for sample `btk-release-live-20260924151922`. The generic `/report/create` Lambda returned a 519,441-byte HTML report with the expected sample, title, full taxonomic breakdown, and top species. The PDF branch timed out in the existing 60-second, 128 MB handler and remains a separate performance follow-up. No raw or clean validation data was deleted.

*Category: validation*

---
*Captured: 2026-09-25*

## Related

_Add links to related pages._
