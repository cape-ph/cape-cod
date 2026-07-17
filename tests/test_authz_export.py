import pytest

# NOTE: capeinfra/__init__ builds resources at import time and needs the mock
# Pulumi config from the session-scoped `config_init` fixture, so the export
# module is imported inside a fixture (after config is set), matching the
# import-inside-fixture convention used by the other tests in this suite.
#
# The Pulumi runtime mocks do not stub the boto3 S3 reads that DatalakeHouse
# performs at construction time, so `@pulumi.runtime.test` cases in this suite
# cannot resolve Outputs here (they share an event loop with the module-level
# datalake build and fail with NoSuchBucket). The Output plumbing of
# build_resource_export is therefore covered by `pulumi preview`, and the
# tributary/bucket iteration is unit-tested via `_collect_export_inputs`.

STANDARD_BUCKET_IDS = {"input-raw", "input-clean", "result-raw", "result-clean"}


@pytest.fixture(scope="module")
def exp():
    from capeinfra.authz import export

    return export


@pytest.mark.parametrize(
    "bucket_id,expected",
    [
        ("input-raw", "raw_uploads"),
        ("input-clean", "clean_uploads"),
        ("result-raw", "raw_results"),
        ("result-clean", "clean_results"),
        ("deployments", "other"),
        ("a-b-c", "other"),
        ("input-weird", "other"),
    ],
)
def test_category_for_bucket_id(exp, bucket_id, expected):
    assert exp._category_for_bucket_id(bucket_id) == expected


def test_resource_record_shape(exp):
    rec = exp._resource_record(
        bucket_name="ccd-dlh-t-hai-input-raw-abc123",
        bucket_arn="arn:aws:s3:::ccd-dlh-t-hai-input-raw-abc123",
        bucket_id="input-raw",
        tributary_code="hai",
        tributary_display_name="hai",
        stack="cape-cod-dev",
    )

    assert set(rec) == {
        "resource_type",
        "resource_identifier",
        "display_name",
        "attributes",
    }
    assert rec["resource_type"] == exp.RESOURCE_TYPE_S3
    assert rec["resource_identifier"] == "s3://ccd-dlh-t-hai-input-raw-abc123/"
    assert rec["display_name"] == "hai Raw Uploads"

    assert rec["attributes"] == {
        "bucket": "ccd-dlh-t-hai-input-raw-abc123",
        "arn": "arn:aws:s3:::ccd-dlh-t-hai-input-raw-abc123",
        "category": "raw_uploads",
        "bucket_role": "input-raw",
        "tributary_code": "hai",
        "environment": "cape-cod-dev",
        "managed_by": exp.MANAGED_BY,
    }


def test_assemble_export_groups_resources_by_tributary(exp):
    tributaries = [
        {"code": "hai", "name": "hai", "description": None},
        {"code": "ds", "name": "Data Science", "description": "ds team"},
    ]
    bucket_meta = [
        ("hai", "hai", "input-raw"),
        ("hai", "hai", "result-clean"),
        ("ds", "Data Science", "input-clean"),
    ]
    resolved = [
        {"name": "hai-raw", "arn": "arn:hai-raw"},
        {"name": "hai-res-clean", "arn": "arn:hai-res-clean"},
        {"name": "ds-clean", "arn": "arn:ds-clean"},
    ]

    export = exp._assemble_export(
        resolved, bucket_meta, tributaries, "cape-cod-dev"
    )

    assert export["version"] == "1.0"
    assert export["pulumi_stack"] == "cape-cod-dev"
    by_code = {t["code"]: t for t in export["tributaries"]}
    assert len(by_code["hai"]["resources"]) == 2
    assert len(by_code["ds"]["resources"]) == 1
    assert by_code["ds"]["description"] == "ds team"
    assert {
        r["attributes"]["category"] for r in by_code["hai"]["resources"]
    } == {"raw_uploads", "clean_results"}


class _FakeBucketRes:
    def __init__(self, name, arn):
        import pulumi

        self.bucket = pulumi.Output.from_input(name)
        self.arn = pulumi.Output.from_input(arn)


class _FakeVersionedBucket:
    def __init__(self, name, arn):
        self.bucket = _FakeBucketRes(name, arn)


class _FakeTributary:
    def __init__(self, code, display_name, description, bucket_ids):
        self.code = code
        self.display_name = display_name
        self.description = description
        self.buckets = {
            bid: _FakeVersionedBucket(
                f"{code}-{bid}-bkt", f"arn:aws:s3:::{code}-{bid}-bkt"
            )
            for bid in bucket_ids
        }


class _FakeDatalakeHouse:
    def __init__(self, tributaries):
        self.tributaries = tributaries


def test_collect_export_inputs_iterates_tributaries_and_buckets(exp):
    dlh = _FakeDatalakeHouse(
        [
            _FakeTributary("hai", "hai", None, ["input-raw", "result-clean"]),
            _FakeTributary(
                "genomics", "Genomics", "genomics team", ["input-clean"]
            ),
        ]
    )

    tributaries, bucket_meta, bucket_outputs = exp._collect_export_inputs(dlh)

    assert tributaries == [
        {"code": "hai", "name": "hai", "description": None},
        {
            "code": "genomics",
            "name": "Genomics",
            "description": "genomics team",
        },
    ]
    expected_bucket_meta = [
        ("genomics", "Genomics", "input-clean"),
        ("hai", "hai", "input-raw"),
        ("hai", "hai", "result-clean"),
    ]
    assert sorted(bucket_meta) == expected_bucket_meta
    # one collected Output per bucket, aligned with bucket_meta
    assert len(bucket_outputs) == len(bucket_meta) == 3
