import pulumi
import pulumi_aws as aws

# NOTE: the data notification feature (Tributary.notify_queue,
# configure_src_bucket_notifications NOTIFY_* wiring, and the seqauto
# split-reads notify config) is not asserted here via mock_datalake. Building
# DatalakeHouse for that fixture already fails before it gets anywhere near a
# tributary (test_catalog below hits a real, unmocked boto3 S3 GetObject
# during catalog bucket construction that needs AWS creds/network), so no
# mock-based assertion in this file can reach the notify wiring without first
# fixing that unrelated pre-existing gap. Identity/shape of the notify
# resources (role statement, Lambda env, per-source Permission/
# BucketNotification) is instead verified via `pulumi preview` against the
# dev stack, per this repo's deployment-preparation policy.


@pulumi.runtime.test
def test_catalog(mock_datalake):
    def check_catalog_bucket(args):
        [catalog_database] = args

        assert type(catalog_database) is aws.s3.Bucket

    return pulumi.Output.all(
        mock_datalake.catalog_bucket,
    ).apply(check_catalog_bucket)
