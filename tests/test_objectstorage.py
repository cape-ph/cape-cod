import pulumi


@pulumi.runtime.test
def test_versionedbucket():
    from capeinfra.objectstorage import VersionedBucket

    name = "TEST-NAME"

    def check_bucket(args):
        bucket_name, bucket_versioning_configuration = args

        assert bucket_name == f"{name}-bucket"
        assert bucket_versioning_configuration["status"] == "Enabled"

    versionedbucket = VersionedBucket(name)
    return pulumi.Output.all(
        versionedbucket.name,
        versionedbucket.versioning.versioning_configuration,
    ).apply(check_bucket)
