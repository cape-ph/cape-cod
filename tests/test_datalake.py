import pulumi
import pulumi_aws as aws


@pulumi.runtime.test
def test_catalog(mock_datalake):
    def check_catalog(args):
        catalog_database, catalog_name = args

        assert catalog_name == f"{mock_datalake.name}-catalog"
        assert type(catalog_database) is aws.glue.CatalogDatabase

    return pulumi.Output.all(
        mock_datalake.catalog.catalog_database,
        mock_datalake.catalog.name,
    ).apply(check_catalog)
