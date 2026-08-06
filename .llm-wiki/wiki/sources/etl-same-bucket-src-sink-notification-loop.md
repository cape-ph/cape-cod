---
type: source
title: "Known issue: same-bucket ETL src=sink can loop via the notifier prefix walk"
slug: etl-same-bucket-src-sink-notification-loop
status: insight
created: 2026-08-04
updated: 2026-08-04
category: architecture
---
# Known issue: same-bucket ETL src=sink can loop via the notifier prefix walk
## Known issue (cape-cod datalake ETL)

The datalake ETL config places no directional constraint on a job's `src` and
`sink`. Bucket names in `pipelines.data.etl[]` are just config keys resolved via
`self.buckets[cfg["src"]]` / `self.buckets[cfg["sink"]]` in
`Tributary.configure_etl` (`capeinfra/datalake/datalake.py`). So all of these
are structurally valid and wireable today:

- clean bucket as `src`, raw bucket as `sink` (e.g. `src: input-clean`,
  `sink: result-raw`)
- the SAME bucket as both `src` and `sink` (the Glue role just gets READ+WRITE
  on that one bucket and `--SINK_BUCKET_NAME` points at it)

What `src`/`sink` actually wire: `src` = S3 trigger attach (`self.sources`) +
Glue role READ grant + the `ETLAttrs` DDB lookup key `(bucket, prefix)`; `sink`
= Glue role WRITE grant + the `--SINK_BUCKET_NAME` job argument the script reads.

### The loop gotcha

Same-bucket `src=sink` is loop-prone, and there is NO infra-level guard - it is
pure config discipline. The trigger notifier
(`assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py`) matches like
this: it takes the new object's key, strips the filename to a directory prefix,
then walks that prefix UPWARD (`prefix.rpartition("/")` in a loop), calling
`EtlTable.get_etls(bucket, prefix)` at each ancestor level. `ETLAttrs` is keyed
`hash_key=bucket_name`, `range_key=prefix`, so each lookup is an EXACT match on a
prefix segment. An object re-triggers the ETL iff some ancestor directory of its
key exactly equals a configured trigger prefix for that bucket AND its suffix is
in that job's `suffixes` list.

Consequence: if an ETL writes its output back into the same bucket under (or
nested beneath) its own trigger prefix with a matching suffix, the output
re-triggers the job -> infinite loop.

### Loop-safety rule

- Write output to a prefix that is neither the trigger prefix nor nested under
  it - a disjoint sibling prefix. Trigger prefix `incoming`, output
  `processed/out.csv` is safe (walk hits `processed`, which matches no configured
  prefix). Output `incoming/done/out.csv` LOOPS (walk reaches `incoming`).
- Suffix is a secondary, more fragile lever: output under the trigger prefix but
  with a suffix outside the trigger's set is ignored, but adding that suffix
  later silently re-arms the loop.

S3 events don't cheaply carry the writing principal, so the notifier can't tell
"a user dropped this" from "our own Glue job wrote this." A by-construction fix
would need something explicit (an excluded output prefix in the filter, or the
notifier ignoring the ETL's own output path). Not built - no one has requested
same-bucket ETL; this was captured while probing what the model permits.

Related: [[sources/obs-2026-08-04-etl-sinks-never-get-s3-notifications-today-notify-type-union]]
(ETL sinks get no notification today; the notify consumer type + union-iteration
assembler is what makes sink-side / clean-bucket reactions expressible).
*Category: architecture*
---
*Captured: 2026-08-04*
## Related
_Add links to related pages._