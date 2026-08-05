import pulumi
import pulumi_aws as aws

# NOTE: the data notification feature (Tributary.notify_queue, the
# configure_src_bucket_notifications NOTIFY_* wiring, the seqauto split-reads
# notify config, and the config-keyed DatalakeHouse.notify_queues
# discoverability map) is not asserted here via mock_datalake. Building
# DatalakeHouse for that fixture already fails before it gets anywhere near a
# tributary (test_catalog below hits a real, unmocked boto3 S3 GetObject
# during catalog bucket construction that needs AWS creds/network), so no
# mock-based assertion in this file can reach the notify wiring or the
# notify_queues map without first fixing that unrelated pre-existing gap.
# notify_queues is a pure config-keyed dict (populated only for tributaries
# that declare notify config), so it adds no AWS resources; its correctness
# and the identity/shape of the notify resources (role statement, Lambda env,
# per-source Permission/BucketNotification) are verified via `pulumi preview`
# against the dev stack, per this repo's deployment-preparation policy.


@pulumi.runtime.test
def test_catalog(mock_datalake):
    def check_catalog_bucket(args):
        [catalog_database] = args

        assert type(catalog_database) is aws.s3.Bucket

    return pulumi.Output.all(
        mock_datalake.catalog_bucket,
    ).apply(check_catalog_bucket)
