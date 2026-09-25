---
type: source
title: "Observation: Taxprofiler Kraken2 report readiness split"
tags:
  - taxprofiler
  - kraken2
  - report
  - readiness
  - etl
  - athena
status: observation
created: 2026-09-25
updated: 2026-09-25
slug: obs-2026-09-25-taxprofiler-kraken2-report-readiness-split
relevance: high
observed_at: 2026-09-25T13:18:41.552Z
source_context: Planning taxprofiler Kraken2 ETL and CAPE report implementation
---

# ⭐ Observation: Taxprofiler Kraken2 report readiness split

Inspected the supplied nf-core/taxprofiler output and legacy Airflow renderer. The primary `output/kraken2/standard-8/*.kraken2.kraken2.report.txt` has the same six-field Kraken2 format expected by the legacy parser, with 1,308 rows and rank variants such as R1, G1, S1, and S2. The execution trace shows the Kraken2 task completing before the MultiQC task; the final `pipeline_info/execution_report_*.html` records successful workflow completion after both. The planned CAPE design therefore separates readiness: the primary report can mark the Kraken2-only report ready if verified as an atomic process output, while MultiQC, params, versions, trace, and full-workflow metadata are auxiliary catalog data. The owner selected one completed run per sample, sampleid as the canonical sample identity, report ID `taxprofiler-kraken2`, semantic/visual legacy compatibility, `/report/create` only, CAPE Cod-only implementation, and retaining clean validation output for review.

*Relevance: high*
*Context: Planning taxprofiler Kraken2 ETL and CAPE report implementation*
*Tags: taxprofiler kraken2 report readiness etl athena*

---
*Observed: 2026-09-25T13:18:41.552Z*
