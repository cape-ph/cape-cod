"""Contains abstractions of object storage for various providers."""

from enum import Enum
from typing import Any, Optional

import boto3
import pulumi_aws as aws
from pulumi import Archive, Asset, ResourceOptions, log

from capepulumi import CapeComponentResource


class Bucket(CapeComponentResource):
    """An object storage location."""

    class PolicyEnum(str, Enum):
        """Enum of supported policy names for this component."""

        read = "read"
        write = "write"
        delete = "delete"
        browse = "browse"
        multipart_upload = "multipart_upload"

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:resources:objectstorage:S3Bucket"

    def __init__(
        self, name, bucket_type="", bucket_name=None, cors_rules=None, **kwargs
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, **kwargs)

        self.name = f"{name}"

        self.bucket = aws.s3.Bucket(
            f"{self.name}-s3",
            bucket=bucket_name,
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} S3 Bucket"},
        )

        self.cors_policy = None
        if cors_rules:
            self.cors_policy = aws.s3.BucketCorsConfiguration(
                f"{self.name}-cors",
                bucket=self.bucket.id,
                cors_rules=cors_rules,
                opts=ResourceOptions(parent=self),
            )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"bucket_name": self.bucket.bucket})

    @property
    def policies(self) -> dict[
        str,
        list[aws.iam.GetPolicyDocumentStatementArgsDict],
    ]:
        if self._policies is None:
            self._policies = dict[
                str,
                list[aws.iam.GetPolicyDocumentStatementArgsDict],
            ]()
            self._policies[self.PolicyEnum.read] = [
                {
                    "effect": "Allow",
                    "actions": ["s3:GetObject", "s3:GetBucketLocation"],
                }
            ]
            self._policies[self.PolicyEnum.write] = [
                {"effect": "Allow", "actions": ["s3:PutObject"]}
            ]
            self._policies[self.PolicyEnum.delete] = [
                {"effect": "Allow", "actions": ["s3:DeleteObject"]}
            ]
            self._policies[self.PolicyEnum.browse] = [
                {"effect": "Allow", "actions": ["s3:ListBucket"]}
            ]
            self._policies[self.PolicyEnum.multipart_upload] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "s3:AbortMultipartUpload",
                        "s3:CreateMultipartUpload",
                        "s3:UploadPart",
                        "s3:CompleteMultipartUpload",
                        "s3:ListParts",
                        "s3:ListMultipartUploads",
                    ],
                }
            ]
        return self._policies

    def add_object(
        self,
        name,
        key,
        source: Asset | Archive,
        import_id: str | None = None,
        **obj_kwargs: Optional[Any],
    ):
        """Adds/imports an object to the versioned bucket.

        `import_id` in this method allows for a pulumi-managed reference to an
        existing bucket object to be made in place of adding a new object.
        Pulumi needs to know about all resources during a deployment, even if
        they already exist.

        Args:
            name: The name of the object to add. acts as the prefix to the
                  resource name when created.
            key: The key to use for the object in the bucket.
            source: A pulumi Asset or archive that is the actual file going
                    into s3.
            import_id: If provided, this will be the pulumi managed id used for
                       the object. Useful for conditionally making a new object
                       vs referencing and existing one.
        Returns:
            The newly created bucket object or an imported reference to an
            existing one.
        """

        return aws.s3.BucketObjectv2(
            f"{self.name}-{name}",
            bucket=self.bucket.id,
            key=key,
            source=source,
            opts=ResourceOptions(parent=self, import_=import_id),
            **obj_kwargs,
        )

    def get_object_contents(self, key, log_missing_keys=False):
        """Return the contents of an object in a VersionedBucket

        Args:
            key: The full object key to get the contents of.
            log_missing_keys: True if a logging message should be recorded for
                              missing keys, False (default) to suppress.

        Returns: The contents of the file as a pulumi Output (bytes) or None if
                 the key is not found.
        """
        # pulumi doesn't really give a way to read existing s3 objects. so we'll
        # fall back to boto3...
        s3_client = boto3.client("s3")

        def apply_fnct(i):
            try:
                response = s3_client.get_object(
                    Bucket=f"{i}",
                    Key=key,
                )
                status = response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )

                if status != 200:
                    err = f"ERROR - Could not get object {key} from s3."
                    log.warn(err, self)
                    return

                return response.get("Body").read()
            except s3_client.exceptions.NoSuchKey:
                if log_missing_keys:
                    log.warn(f"Requested object key {key} does not exist")
                return None

        return self.bucket.id.apply(lambda i: apply_fnct(i))


class VersionedBucket(Bucket):
    """An object storage location with versioning turned on."""

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:resources:objectstorage:S3VersionedBucket"

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)

        self.versioning = aws.s3.BucketVersioning(
            f"{self.name}-vrsn",
            bucket=self.bucket.id,
            versioning_configuration=aws.s3.BucketVersioningVersioningConfigurationArgs(
                status="Enabled",
            ),
            opts=ResourceOptions(parent=self),
        )
