---
type: source
title: "Observation: Branch 363 demo decisions: reuse result-clean crawler (#364) and single data function (#365)"
slug: obs-2026-08-06-branch-363-demo-decisions-reuse-result-clean-crawler-364-and
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: high
observed_at: 2026-08-06T18:10:49.549Z
tags: ["cape-cod", "datalake", "etl", "caerbannog", "seqauto", "crawler", "report", "data-function", "branch-363"]
source_context: "Q&A planning for branch 363 caerbannog result ETL + report; filed P1 issues #364 and #365"
---
# ⭐ Observation: Branch 363 demo decisions: reuse result-clean crawler (#364) and single data function (#365)
On branch 363 (new seqauto raw-result ETL for the caerbannog consumer output + report update), two design decisions took the low-churn path for the demo and deferred the proper fix to new P1 issues.

Crawler: reuse the existing seqauto result-clean crawler rather than standing up a per-source crawler. Crawlers are one-per-bucket today (configure_bucket in capeinfra/datalake/datalake.py builds a single DataCrawler from one crawler: config block; the crawler prefix is the Glue table-name prefix and it walks the whole bucket, turning each top-level folder into a result_<folder> table - which is why the bactopia data function queries result_software_versions, result_amrfinderplus, result_sourmash_gtdb_rs207_k31). The new caerbannog ETL will write outputs as distinct top-level folders under result-clean (e.g. aggregate/, stoplight/, cluster_estimates/) so the existing crawler auto-discovers them as result_aggregate/result_stoplight/result_cluster_estimates with zero infra change, coexisting with bactopia tables for the demo. Redesign deferred to issue #364 (redesign clean result layout + move to columnar Parquet/Iceberg crawl format + support many crawlers per bucket).

Report data function: fold the new caerbannog Athena queries into the existing single bactopia-single-sample-analysis data function (assets/report/bactopia-single-sample-analysis/data_function.py) and add table(s) to the template, bumping the funct_args timeout if the extra serial queries exceed 45s. The report payload shape is NOT a constraint - the data function returns a free-form dict passed straight to template.render, so one function can carry many query result sets. Composable mix-and-match data functions deferred to issue #365 (needs config schema, capemeta.py N-lambda build, canned-report DDB contract + capepy CannedReportTable.get_report change, handler multi-invoke + namespaced merge, concurrent invocation).
*Relevance: high*

*Context: Q&A planning for branch 363 caerbannog result ETL + report; filed P1 issues #364 and #365*

*Tags: cape-cod datalake etl caerbannog seqauto crawler report data-function branch-363*
---
*Observed: 2026-08-06T18:10:49.549Z*