"""Contains abstractions of object storage for various providers."""

# TODO: figure out the best way to lay this out to allow easily switch between
#       aws, gcp, and azure (we're only implementing aws at this time though)

import pulumi_aws as aws
from pulumi import Archive, Asset, ComponentResource, ResourceOptions


class VersionedBucket(ComponentResource):
    """An object storage location with versioning turned on."""

    def __init__(self, name, opts=None):
        # This maintains parental relationships within the pulumi stack
        super().__init__(
            "capeinfra:objectstorage:S3VersionedBucket", name, None, opts
        )

        self.name = f"{name}-bucket"

        self.bucket = aws.s3.BucketV2(
            f"{self.name}", opts=ResourceOptions(parent=self)
        )

        self.versioning = aws.s3.BucketVersioningV2(
            f"{name}-versioning",
            bucket=self.bucket.id,
            versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(
                status="Enabled"
            ),
            opts=ResourceOptions(parent=self),
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"bucket_name": self.bucket.bucket})

    def add_object(self, name, key, source: Asset | Archive):
        """Adds an object to the versioned bucket.

        Args:
            name: The name of the object to add. acts as the prefix to the
                  resource name when created.
            key: The key to use for the object in the bucket.
            source: A pulumi Asset or archive that is the actual file going
                    into s3.
        Returns:
            The newly created bucket object.
        """
        return aws.s3.BucketObjectv2(
            f"{self.name}-{name}",
            bucket=self.bucket.id,
            key=key,
            source=source,
            opts=ResourceOptions(parent=self),
        )
