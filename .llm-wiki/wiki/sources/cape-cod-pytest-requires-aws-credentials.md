---
type: source
title: "cape-cod pytest suite requires valid AWS credentials"
slug: cape-cod-pytest-requires-aws-credentials
status: insight
created: 2026-07-13
updated: 2026-07-13
category: testing
---
# cape-cod pytest suite requires valid AWS credentials
In the `cape-cod` Pulumi IaC repo, the `tests/` pytest suite is only partially
mocked. `tests/conftest.py` sets `pulumi.runtime.set_mocks(PulumiMock())`, but
Pulumi mocks intercept only Pulumi resource registration and provider `call`s -
they do NOT intercept direct `boto3` calls made in Python during construct
construction. Building `CapeMeta` / `DatalakeHouse` (the `mock_meta` /
`mock_datalake` fixtures) performs real S3 `GetObject` calls, so the suite needs
valid, unexpired AWS credentials.

With expired/absent credentials, both `test_capemeta.py::test_asset_bucket` and
`test_datalake.py::test_catalog` fail with
`botocore.exceptions.ClientError: ... (ExpiredToken) ... GetObject`. That is an
environment/credentials problem, not a code regression - refresh credentials
before trusting a pytest result. Layer fixtures also pip-install `capepy==3.0.0`
during setup (expected), and `s3.BucketV2` deprecation warnings are benign
pulumi_aws version drift. CI does not run pytest at all
(`python_checks.yml@v1` with `pytest: false`).

See [[concepts/testing-and-pulumi-preview-workflow]] and
[[concepts/agent-playbook]].
*Category: testing*
---
*Captured: 2026-07-13*
## Related
_Add links to related pages._