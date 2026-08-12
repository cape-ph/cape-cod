---
type: source
title: "Observation: MWAA report perms broadened to all tributary crawlers, refactored to compose-statements IAM pattern"
tags:
  - airflow
  - mwaa
  - iam
  - glue
  - lambda
  - reports
  - patterns
status: observation
created: 2026-08-12
updated: 2026-08-12
slug: obs-2026-08-12-mwaa-report-perms-broadened-to-all-tributary-crawlers-refact
relevance: high
observed_at: 2026-08-12T19:10:50.912Z
source_context: Aligning MWAA report-generation perms with repo IAM compose pattern and broadening crawler scope
---

# ⭐ Observation: MWAA report perms broadened to all tributary crawlers, refactored to compose-statements IAM pattern

Refined the MWAA report-generation perms wiring in cape-cod. Two changes: (1) broadened crawler access from just the seqauto result-clean crawler to every crawler attached to any tributary - PrivateSwimlane.configure_report_generation_perms now builds crawler_arns = [crawler.crawler.arn for trib in capeinfra.data_lakehouse.tributaries for crawler in trib.crawlers.values()], dropping the seqauto-specific next()/`.get("result-clean")` lookup. (2) Refactored MwaaEnvironment.configure_report_generation_policy to the repo's favored "NEW IAM MODULE" compose pattern instead of hand-rolled Output.json_dumps + managed aws.iam.Policy + RolePolicyAttachment. It now builds GetPolicyDocumentStatementArgsDict statements, fills ARNs via iam.add_resources inside Output applies, combines with iam.aggregate_statements, and attaches a single inline aws.iam.RolePolicy via aws.iam.get_policy_document_output(...).json - mirroring how get_inline_role and MwaaEnvironment.__init__ build the execution role. Signature changed to crawler_arns: list[Input[str]]. This avoids the 20-policy attachment limit and matches the direction the iam.py comments endorse (resource-provided/composed statements over get_api_statements). Note: DataCrawler does not yet expose a `policies` property like buckets/MwaaEnvironment do; the glue crawl statement is defined inline in the method since the report lambda (a raw aws.lambda_.Function inside CapeRestApi) can't expose one symmetrically.

*Relevance: high*
*Context: Aligning MWAA report-generation perms with repo IAM compose pattern and broadening crawler scope*
*Tags: airflow mwaa iam glue lambda reports patterns*

---
*Observed: 2026-08-12T19:10:50.912Z*
