import pulumi
import pulumi_aws as aws


@pulumi.runtime.test
def test_catalog(mock_datalake):
    def check_catalog_bucket(args):
        [catalog_database] = args

        assert type(catalog_database) is aws.s3.Bucket

    return pulumi.Output.all(
        mock_datalake.catalog_bucket,
    ).apply(check_catalog_bucket)
