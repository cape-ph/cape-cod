import pulumi


@pulumi.runtime.test
def test_asset_bucket(mock_meta):
    def check_versioning_configuration(versioning_configuration):
        assert versioning_configuration["status"] == "Enabled"

    versionedbucket = mock_meta.automation_assets_bucket
    return versionedbucket.versioning.versioning_configuration.apply(
        check_versioning_configuration
    )
