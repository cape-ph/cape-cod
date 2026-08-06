---
type: source
title: "ETL never triggers: notifier ETL_ATTRS_DDB_TABLE env uses logical name, misses -DDBT physical suffix"
slug: etl-notifier-ddb-table-name-mismatch
status: insight
created: 2026-08-05
updated: 2026-08-05
category: bugfix
---
# ETL never triggers: notifier ETL_ATTRS_DDB_TABLE env uses logical name, misses -DDBT physical suffix
Definitive root cause of "S3 upload to unprocessed/ never fires the ETL" for seqauto (and every tributary using this path).

**Symptom:** notifier Lambda `ccd-dlh-T-seqauto-lmbdtrgfnct-*` is invoked on each `s3:ObjectCreated:*` but crashes on every invocation with:
```
AccessDeniedException ... not authorized to perform: dynamodb:DescribeTable
  on resource: table/ccd-dlh-ETLAttrs
  File ".../capepy/aws/dynamodb.py", line 30, in __init__  ->  self.table.load()
  File "/var/task/index.py", line 69  ->  ddb_table = EtlTable()
```
It dies at `EtlTable()` construction (capepy's `Table.__init__` unconditionally calls `self.table.load()`, a DescribeTable) before ever reading ETL attrs or sending to the queue.

**Root cause = DynamoDB table-name mismatch:**
- Notifier env `ETL_ATTRS_DDB_TABLE = ccd-dlh-ETLAttrs` (the logical/component name).
- Real table AND the role's IAM grant = `ccd-dlh-ETLAttrs-DDBT` (only that table exists).
- capepy `EtlTable()` reads `os.getenv("ETL_ATTRS_DDB_TABLE")` -> queries `ccd-dlh-ETLAttrs`, which is neither the real table nor in the role allow-list -> AccessDenied on DescribeTable.

**Where the bug is (`capeinfra/`, NOT the split-reads branch):**
- `capeinfra/resources/database.py`: `DynamoTable.__init__` sets `self.name = name` but creates the physical table as `aws.dynamodb.Table(f"{self.name}-ddbt", name=f"{self.name}-DDBT", ...)`, exposed as `self.ddb_table.name`. The `-DDBT` physical suffix landed in commit 7b41e705 (Pihera, 2025-12-09).
- `capeinfra/datalake/datalake.py:593`: notifier env is `"ETL_ATTRS_DDB_TABLE": etl_attrs_ddb_table.name` (logical), while the IAM policy correctly uses `etl_attrs_ddb_table.ddb_table.arn` (physical `-DDBT`). That divergence is the bug.

**Fix (one line):** `datalake.py:593` -> `"ETL_ATTRS_DDB_TABLE": etl_attrs_ddb_table.ddb_table.name`. Requires a deploy. Since it is shared infra affecting ALL tributaries (genomics, hai, seqauto) since 2025-12-09, it is arguably its own hotfix/PR rather than folded into the seqauto split-reads branch. The read policy already correctly includes DescribeTable/GetItem/Query/Scan on the physical ARN, so no IAM change is needed.

**Fast test-unblock (mutating, gated):** `aws lambda update-function-configuration --function-name ccd-dlh-T-seqauto-lmbdtrgfnct-* --environment "Variables={ETL_ATTRS_DDB_TABLE=ccd-dlh-ETLAttrs-DDBT,...}"` temporarily repoints the running Lambda so Phase 1 can be tested immediately. Caveat: out-of-band from Pulumi; a later `pulumi up` reverts it and it shows as preview drift.

**Confirmed-healthy (rules out other causes):** object landed at `unprocessed/plainreads-fastq.tar.gz` in the real input-raw bucket `ccd-dlh-t-seqauto-input-raw-vbkt-s3-b8fded5`; bucket notification is wired to the notifier; the DDB row in `ccd-dlh-ETLAttrs-DDBT` is correct (`bucket_name=...input-raw..., prefix=unprocessed, suffixes=[gz,tar], sink=...input-clean..., etl_job=ccd-dlh-T-seqauto-ETL-seqreadarch-003945d`). Once the table name is fixed, `.gz` matches and the ETL will enqueue.

**Naming gotcha:** the string `ccd-dlh-T-seqauto-ETL-seqreadarch-003945d` (which looked like a bucket) is actually the `etl_job` value / Glue job resource name stored in the DDB row - not an S3 bucket. S3 bucket names are lowercase-only, so the uppercase T/ETL are a tell it is a Pulumi resource name.

Related: [[sources/obs-2026-08-04-ddb-row-verified-correct-tar-gz-unprocessed-trigger-failure-]], [[sources/obs-2026-08-04-direct-s3-dump-to-unprocessed-did-not-fire-the-etl-suspected]].
*Category: bugfix*
---
*Captured: 2026-08-05*
## Related
_Add links to related pages._