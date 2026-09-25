---
type: source
title: Taxprofiler Kraken2 ETL report implementation
status: insight
category: architecture
created: 2026-09-25
updated: 2026-09-25
slug: taxprofiler-kraken2-etl-report-implementation
---

# Taxprofiler Kraken2 ETL report implementation

Implemented the approved taxprofiler Kraken2 path in [[entities/pipeline-data-module]] and the CAPE canned-report system. The new ETL parses the full Kraken2 report and selected MultiQC, params, versions, execution trace, and completion metadata into collision-free result-clean CSV partitions. The new `taxprofiler-kraken2` report queries `result_kraken2_taxa` through Athena and preserves the legacy summary cards, top-species table, and interactive taxonomy tree from the Airflow renderer. The generic `/report/create` route is reused. Read-only AWS inspection validated the supplied 73-object S3 prefix and existing seqauto Glue catalog/crawler. The required Pulumi preview succeeded with the expected new ETL/report resources, but also exposed three unrelated destructive local-dev Cognito drift deletes; no deployment was run and those deletes require owner review.

*Category: architecture*

---
*Captured: 2026-09-25*

## Related

_Add links to related pages._
