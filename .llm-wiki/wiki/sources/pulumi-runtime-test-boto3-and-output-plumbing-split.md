---
type: source
title: "Pulumi runtime tests can't resolve boto3-backed Outputs; split pure logic from Output plumbing"
slug: pulumi-runtime-test-boto3-and-output-plumbing-split
status: insight
created: 2026-07-14
updated: 2026-07-14
category: testing
---
# Pulumi runtime tests can't resolve boto3-backed Outputs; split pure logic from Output plumbing
In `cape-cod`, `@pulumi.runtime.test` cases share one asyncio event loop and `wait_for_rpcs` awaits ALL pending resource RPCs - including those from `capeinfra/__init__`'s module-level `data_lakehouse = DatalakeHouse(...)` build. That build resolves Outputs backed by `Bucket.get_object_contents`, which calls boto3 S3 GetObject against buckets the Pulumi mocks never really create -> `botocore.errorfactory.NoSuchBucket`. So any runtime-test in the suite fails locally once `capeinfra` is imported, even a hermetic test that creates no AWS resources of its own (the failure comes from the shared loop, not the test). This is the same reason the pre-existing `test_capemeta::test_asset_bucket` and `test_datalake::test_catalog` fail in a sandbox. See [[concepts/testing-and-pulumi-preview-workflow]] and [[sources/cape-cod-pytest-requires-aws-credentials]].

Pattern that works: split the code under test into (a) pure, dict-in/dict-out functions and (b) a thin `Output.all(...).apply(...)` wrapper. Unit-test (a) directly with no runtime (fast, deterministic, green anywhere), and cover the trivial Output glue via `pulumi preview` instead. For the export I extracted `_collect_export_inputs` (pure iteration over tributaries/buckets, collecting but not resolving Output objects), `_resource_record`, and `_assemble_export`; `build_resource_export` just wires them through `Output.all(...).apply(...)`. Result: 10 runtime-free tests pass locally; no dependence on the broken mock+boto3 path.

Two more gotchas confirmed 2026-07-14: (1) `pulumi preview` needs network egress to the S3 state backend `s3://cape-pulumi-state/cape-cod` (us-east-2); in a DNS/network-isolated sandbox it fails with `dial tcp: lookup ... i/o timeout` on `.pulumi/meta.yaml` even with a valid AWS token, and `GODEBUG=netdns=cgo` does not help. (2) pyright's persistent LSP server negative-caches a not-yet-existing import; after creating a new package (`capeinfra/authz/`), `reportMissingImports` persisted through reopen even though runtime import, `py_compile`, and `ruff` were all clean - a stale-server false positive, not a real error.
*Category: testing*
---
*Captured: 2026-07-14*
## Related
_Add links to related pages._