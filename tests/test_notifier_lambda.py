"""Unit tests for the S3->SQS notifier Lambda's pure notification helpers.

These cover ``match_notify_rules`` and ``build_notify_message``, the two
side-effect-free functions in the data notification path of
``assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py``. The
existing ETL-message path in that Lambda is untouched by this feature and is
not re-tested here.

The Lambda module calls ``boto3.client("sqs")`` at import time, which needs a
region (but not credentials) to succeed, so ``AWS_DEFAULT_REGION`` is set
before the module is loaded. It is a single-file Lambda (not importable as a
package), so it is loaded from its source path, matching the
import-inside-fixture convention used elsewhere in this suite (see
test_workflow_user_attribution.py).
"""

import importlib.util
import os

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module(name, relpath):
    path = os.path.join(REPO_ROOT, relpath)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def notifier():
    return _load_module(
        "new_s3obj_queue_notifier_lambda",
        "assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py",
    )


@pytest.fixture(scope="module")
def rules():
    return {
        "input-clean-bucket": [
            {
                "name": "split-reads",
                "prefix": "sequencing-reads-split",
                "suffixes": [],
            },
            {
                "name": "split-reads-tsv",
                "prefix": "sequencing-reads-split",
                "suffixes": ["tsv"],
            },
        ]
    }


class TestMatchNotifyRules:
    def test_prefix_match_hit(self, notifier, rules):
        matched = notifier.match_notify_rules(
            "input-clean-bucket",
            "sequencing-reads-split/sample1.txt",
            rules,
        )

        assert "split-reads" in matched

    def test_prefix_miss(self, notifier, rules):
        matched = notifier.match_notify_rules(
            "input-clean-bucket",
            "other-prefix/sample1.txt",
            rules,
        )

        assert matched == []

    def test_wrong_bucket_miss(self, notifier, rules):
        matched = notifier.match_notify_rules(
            "some-other-bucket",
            "sequencing-reads-split/sample1.txt",
            rules,
        )

        assert matched == []

    def test_suffix_filter_hit(self, notifier, rules):
        matched = notifier.match_notify_rules(
            "input-clean-bucket",
            "sequencing-reads-split/sample1.tsv",
            rules,
        )

        assert "split-reads-tsv" in matched

    def test_suffix_filter_miss(self, notifier, rules):
        matched = notifier.match_notify_rules(
            "input-clean-bucket",
            "sequencing-reads-split/sample1.txt",
            rules,
        )

        assert "split-reads-tsv" not in matched

    def test_empty_suffixes_matches_any(self, notifier, rules):
        matched = notifier.match_notify_rules(
            "input-clean-bucket",
            "sequencing-reads-split/sample1.anything",
            rules,
        )

        assert "split-reads" in matched

    def test_absent_suffixes_matches_any(self, notifier):
        rules_without_suffixes = {
            "bkt": [{"name": "no-suffixes-key", "prefix": "pfx"}]
        }

        matched = notifier.match_notify_rules(
            "bkt", "pfx/anything.weird", rules_without_suffixes
        )

        assert matched == ["no-suffixes-key"]

    def test_multiple_rules_return_multiple_names(self, notifier, rules):
        matched = notifier.match_notify_rules(
            "input-clean-bucket",
            "sequencing-reads-split/sample1.tsv",
            rules,
        )

        assert set(matched) == {"split-reads", "split-reads-tsv"}


class TestBuildNotifyMessage:
    def test_builds_all_fields(self, notifier):
        raw_record = {
            "eventTime": "2024-01-01T00:00:00.000Z",
            "eventName": "ObjectCreated:Put",
            "s3": {
                "object": {
                    "size": 1234,
                    "eTag": "abc123",
                }
            },
        }

        msg = notifier.build_notify_message(
            raw_record,
            "input-clean-bucket",
            "sequencing-reads-split/sample1.tsv",
            "seqauto",
            "split-reads",
        )

        assert msg == {
            "schema_version": "1",
            "event_time": "2024-01-01T00:00:00.000Z",
            "event_name": "ObjectCreated:Put",
            "bucket": "input-clean-bucket",
            "key": "sequencing-reads-split/sample1.tsv",
            "size": 1234,
            "etag": "abc123",
            "tributary": "seqauto",
            "notification": "split-reads",
        }

    def test_missing_etag_tolerated(self, notifier):
        raw_record = {
            "eventTime": "2024-01-01T00:00:00.000Z",
            "eventName": "ObjectCreated:Put",
            "s3": {"object": {"size": 1234}},
        }

        msg = notifier.build_notify_message(
            raw_record,
            "input-clean-bucket",
            "sequencing-reads-split/sample1.tsv",
            "seqauto",
            "split-reads",
        )

        assert msg["etag"] is None
        assert msg["size"] == 1234
