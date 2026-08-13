---
type: source
title: "Observation: Writing from a capepy EtlJob to a non-sink bucket needs artifacts_bucket wiring + getResolvedOptions"
tags:
  - etl
  - glue
  - capepy
  - s3
  - airflow
  - reports
  - rabits
  - caerbannog
status: observation
created: 2026-08-12
updated: 2026-08-12
slug: obs-2026-08-12-writing-from-a-capepy-etljob-to-a-non-sink-bucket-needs-arti
relevance: high
observed_at: 2026-08-12T19:27:21.790Z
source_context: Redirecting the RABiTS report ETL output to the seqauto artifacts bucket
---

# ⭐ Observation: Writing from a capepy EtlJob to a non-sink bucket needs artifacts_bucket wiring + getResolvedOptions

To write from a capepy Glue EtlJob to a bucket other than its configured sink (result-clean), you must thread the extra bucket in yourself - there is no built-in. Pattern used for the RABiTS/caerbannog report: (1) capeinfra/pipeline/data.py EtlJob.__init__ gained an optional artifacts_bucket: VersionedBucket | None = None kwarg; when set it adds a VersionedBucket.PolicyEnum.write add_resources block to the etl_role aggregate_statements (mirroring the sink block, `for bucket in ([artifacts_bucket] if artifacts_bucket else [])`) and sets default_args['--ARTIFACTS_BUCKET_NAME'] = artifacts_bucket.bucket. (2) capeinfra/datalake/datalake.py configure_etl passes artifacts_bucket=self.buckets.get('artifacts') (seqauto has an 'artifacts' bucket; other tributaries pass None safely). (3) The ETL script reads the new arg via awsglue.utils.getResolvedOptions(sys.argv, ['ARTIFACTS_BUCKET_NAME']) - capepy's EtlJob only resolves SRC_BUCKET_NAME/OBJECT_KEY/SINK_BUCKET_NAME into etl_job.parameters, so any extra job arg needs a direct getResolvedOptions call - then writes with etl_job.get_client('s3').put_object(Bucket=..., Key=..., Body=...) instead of write_sink_file (which is hardwired to SINK_BUCKET_NAME). Boto3Object.get_client exists in capepy/aws/meta.py. Also: the ast-grep no-init-return rule false-positives on a `return` inside a nested closure defined within __init__ (data.py add_to_python_modules); pyright is clean, ignore it. And 'rabits' had to be added to .typos.toml [default.extend-words] since RABiTS is the product name.

*Relevance: high*
*Context: Redirecting the RABiTS report ETL output to the seqauto artifacts bucket*
*Tags: etl glue capepy s3 airflow reports rabits caerbannog*

---
*Observed: 2026-08-12T19:27:21.790Z*
