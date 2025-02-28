"""Contains resources used by the whole CAPE infra deployment."""

import pulumi_aws as aws
from pulumi import FileArchive, FileAsset, Output, ResourceOptions

from capeinfra.resources.objectstorage import VersionedBucket
from capepulumi import CapeComponentResource


class CapeMeta(CapeComponentResource):
    """Contains resources needed by all parts of the infra."""

    def __init__(self, name, **kwargs):
        # This maintains parental relationships within the pulumi stack
        super().__init__(
            "capeinfra:meta:capemeta:CapeMeta",
            name,
            config="meta",
            **kwargs,
        )
        self.automation_assets_bucket = VersionedBucket(
            f"{name}-assets-vbkt",
            desc_name=f"{self.desc_name} automation assets",
            opts=ResourceOptions(parent=self),
        )

        for etl_def in self.config.get("glue", "etl", default=[]):
            self.automation_assets_bucket.add_object(
                etl_def["name"],
                key=etl_def["key"],
                # NOTE: These should always be file assets in the ETL case
                #       (as opposed to archive assets)
                source=FileAsset(etl_def["srcpth"]),
            )

        self.capepy = CapePy(self.automation_assets_bucket)
        self.users = CapeUsers()

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs(
            {
                "cape-meta-automation-assets-bucket": self.automation_assets_bucket.bucket
            }
        )


class CapePy(CapeComponentResource):
    def __init__(self, assets_bucket: VersionedBucket, **kwargs):
        self.name = "capepy"
        super().__init__(
            "capeinfra:meta:capemeta:CapePy",
            self.name,
            desc_name="Resources for distributing the CapePy library",
            **kwargs,
        )

        self.bucket = assets_bucket
        capepy_whl = "capepy-2.0.0-py3-none-any.whl"
        self.object = self.bucket.add_object(
            f"{self.name}-object",
            key=capepy_whl,
            source=FileAsset(f"./assets/capepy/{capepy_whl}"),
        )

        self.uri = Output.all(
            bucket=self.bucket.bucket.bucket, key=self.object.key
        ).apply(lambda args: f"s3://{args['bucket']}/{args['key']}")

        self.lambda_layer = aws.lambda_.LayerVersion(
            f"{self.name}-lmbd-lyr",
            layer_name=self.name,
            description="This layer provides the capepy Python library",
            license_info=" Apache-2.0",
            compatible_runtimes=["python3.10"],
            code=FileArchive("./assets/capepy/capepy_layer.zip"),
            opts=ResourceOptions(parent=self),
        )


class CapeUsers(CapeComponentResource):
    def __init__(self, **kwargs):
        self.name = "cape-users"
        super().__init__(
            "capeinfra:meta:capemeta:CapeUsers",
            self.name,
            desc_name="Resources for user management in the CAPE infrastructure",
            **kwargs,
        )

        self.user_pool = aws.cognito.UserPool(
            "cape-users",
            name="cape-users",
            account_recovery_setting={
                "recovery_mechanisms": [
                    {"name": "verified_email", "priority": 1}
                ]
            },
            admin_create_user_config={"allow_admin_create_user_only": True},
            password_policy={
                "minimum_length": 8,
                "require_lowercase": True,
                "require_numbers": True,
                "require_symbols": True,
                "require_uppercase": True,
                "temporary_password_validity_days": 5,
            },
            auto_verified_attributes=["email"],
            username_attributes=["email"],
        )

        # TODO: configure external providers with IdentifyProvider
        # aws.cognito.IdentityProvider("name", user_pool_id=self.user_pool.id,
        #                              provider_name="GTRI", provider_type="OIDC",
        #                              ...)
