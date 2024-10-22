"""Contains abstractions of object storage for various providers."""

from typing import Any, Optional

import pulumi_aws as aws
from pulumi import Archive, Asset, ResourceOptions

from .pulumi import CapeComponentResource


class VersionedBucket(CapeComponentResource):
    """An object storage location with versioning turned on."""

    def __init__(self, name, bucket_name=None, **kwargs):
        # This maintains parental relationships within the pulumi stack
        super().__init__(
            "capeinfra:resources:objectstorage:S3VersionedBucket",
            name,
            **kwargs,
        )

        self.name = f"{name}"

        self.bucket = aws.s3.BucketV2(
            f"{self.name}-s3",
            bucket=bucket_name,
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} S3 Bucket"},
        )

        self.versioning = aws.s3.BucketVersioningV2(
            f"{self.name}-vrsn",
            bucket=self.bucket.id,
            versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(
                status="Enabled",
            ),
            opts=ResourceOptions(parent=self),
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"bucket_name": self.bucket.bucket})

    def add_object(
        self, name, key, source: Asset | Archive, **obj_kwargs: Optional[Any]
    ):
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
            **obj_kwargs,
        )
