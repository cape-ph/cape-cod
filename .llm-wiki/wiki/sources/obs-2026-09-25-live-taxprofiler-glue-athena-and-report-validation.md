---
type: source
title: "Observation: Live taxprofiler Glue Athena and report validation"
tags:
  - taxprofiler
  - glue
  - athena
  - report
  - aws
  - validation
status: observation
created: 2026-09-25
updated: 2026-09-25
slug: obs-2026-09-25-live-taxprofiler-glue-athena-and-report-validation
relevance: critical
observed_at: 2026-09-25T15:24:13.782Z
source_context: Post-deployment live validation of taxprofiler Kraken2 ingestion and report
---

# 🔴 Observation: Live taxprofiler Glue Athena and report validation

After owner deployment, live validation succeeded against s3://ccd-dlh-t-seqauto-result-raw-vbkt-s3-1e80821/taxprofiler-output/btk-release-live-20260924151922. The deployed Glue ETL wrote kraken2_taxa and kraken2_summary clean objects; the seqauto result-clean crawler succeeded; Athena exposed result_kraken2_taxa with 1,308 rows and result_kraken2_summary with one row, partitions sample_id and database_id=standard-8. The deployed data Lambda returned success with 391,912 total reads, 248,629 classified, 143,283 unclassified, 1,306 distinct taxa, and Bacillus thuringiensis as top species. The generic /report/create Lambda returned HTTP 200 HTML of 519,441 bytes with expected report markers. All 17 supported raw objects had successful Glue ETL runs, and the second crawler exposed 10 nonempty auxiliary taxprofiler tables. PDF invocation timed out at the existing 60-second 128 MB generic handler limit; HTML is validated. No raw or clean data was deleted.

*Relevance: critical*
*Context: Post-deployment live validation of taxprofiler Kraken2 ingestion and report*
*Tags: taxprofiler glue athena report aws validation*

---
*Observed: 2026-09-25T15:24:13.782Z*
