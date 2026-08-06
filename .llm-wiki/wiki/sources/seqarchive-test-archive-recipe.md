---
type: source
title: "Building valid test archives for the seqarchive ETL"
slug: seqarchive-test-archive-recipe
status: insight
created: 2026-08-04
updated: 2026-08-04
category: devops
---
# Building valid test archives for the seqarchive ETL
Recipe for building a valid input archive for the `seqreadarch` (etl_seqarchive.py) ETL, verified by simulating the real ETL logic.

**Archive:** a tar, plain or gzipped - the ETL opens it with `tarfile.open(fileobj=..., mode="r")` (transparent mode), so both `.tar` and `.tar.gz` read correctly.

**Internal layout:**
```
meta.json                       (at archive root)
sequencing/<read files>         (fasta/fastq, gz or not)
```
A bare `sequencing/` directory entry is harmless: `TarFile.getnames()` reports it WITHOUT a trailing slash, so the ETL's `startswith("sequencing/")` filter excludes it and the member loop only sees real files.

**meta.json required keys:** `sampleId`, `sampleType`, `sampleMatrix`, `sampleCollectionLocation`, `sampleCollectionDate`. `sampleId` drives every clean-sink path: `sample_id=<id>/year=.../month=.../day=.../hour=.../minute=.../second=...`. Example real value: `{"sampleId":"abcdefghij","sampleType":"Environmental","sampleMatrix":"Soil","sampleCollectionLocation":"Back yard","sampleCollectionDate":"2025-08-15T14:36:28.024649+00:00"}`.

**ETL behavior per member:** names ending `fasta`/`fastq` are gzipped in place; anything else passes through as-is.

**Upload target:** the seqauto input-raw bucket under `unprocessed/` (ETL `suffixes: [gz, tar]`).

**Test artifacts built this session** (copies only; source data at `/home/lp76/projects/cape/test-data/seqauto/` untouched), at `/home/lp76/projects/cape/test-data/seqauto/etl-split-test/`:
- `plainreads-fastq.tar.gz` - 3 UNCOMPRESSED `.fastq` members `plainreads_part{A,B,C}.fastq`, `sampleId=plainreads`.
- `gzreads-fastqgz.tar.gz` - 3 `.fastq.gz` members `gzreads_part{A,B,C}.fastq.gz`, `sampleId=gzreads`.
Distinct sample ids + filename prefixes make the split outputs obvious. See [[sources/seqauto-etl-s3-trigger-mechanics]] for how upload triggers the run.
*Category: devops*
---
*Captured: 2026-08-04*
## Related
_Add links to related pages._