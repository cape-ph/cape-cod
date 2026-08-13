---
type: source
title: "Observation: MWAA report-generation perms wired via configure_report_generation_policy"
tags:
  - airflow
  - mwaa
  - iam
  - glue
  - lambda
  - reports
  - bactopia
status: observation
created: 2026-08-12
updated: 2026-08-12
slug: obs-2026-08-12-mwaa-report-generation-perms-wired-via-configure-report-gene
relevance: high
observed_at: 2026-08-12T18:46:57.666Z
source_context: Finalizing cape-cod support for the bactopia_kraken2 workflow report step
---

# ⭐ Observation: MWAA report-generation perms wired via configure_report_generation_policy

Granted the MWAA execution role the perms the bactopia_kraken2 generate_and_store_report DAG task needs. Added MwaaEnvironment.configure_report_generation_policy(crawler_arn, report_lambda_arn) in capeinfra/pipeline/airflow.py, mirroring the existing configure_batch_* pattern (create aws.iam.Policy + RolePolicyAttachment). It grants glue:StartCrawler + glue:GetCrawler scoped to the crawler ARN and lambda:InvokeFunction scoped to the report lambda ARN. Wired real ARNs (not hardcoded physical names): the seqauto tributary result-clean crawler via capeinfra.data_lakehouse.tributaries (filter t.code == "seqauto", then .crawlers["result-clean"].crawler.arn), and the getcannedreport handler lambda via a new public CapeRestApi.get_handler_lambda_arn(name) accessor that searches the private _ids_to_lambdas mapping by config handler name. New PrivateSwimlane.configure_report_generation_perms() resolves both and is called after create_private_api_resources() (the api/lambda is created after the MWAA env, so wiring must be post-hoc, like the batch policies). Guards to no-op if MWAA env or resources are unresolved. s3:PutObject is already covered by the AmazonS3FullAccess attachment.

*Relevance: high*
*Context: Finalizing cape-cod support for the bactopia_kraken2 workflow report step*
*Tags: airflow mwaa iam glue lambda reports bactopia*

---
*Observed: 2026-08-12T18:46:57.666Z*
