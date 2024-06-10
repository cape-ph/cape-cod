"""Contains resources used by the whole CAPE infra deployment."""

import pulumi_aws as aws
from pulumi import ComponentResource, Config, FileAsset, ResourceOptions

from ..objectstorage import VersionedBucket


class CapeMeta(ComponentResource):
    def __init__(self, name, opts=None):
        # By calling super(), we ensure any instantiation of this class
        # inherits from the ComponentResource class so we don't have to declare
        # all the same things all over again.
        super().__init__("capeinfra:meta:capemeta:CapeMeta", name, None, opts)

        # TODO:
        # - automation asset bucket (scripts, etc)
        # - etl scripts (until we have these repos deploying themselves)

        # The parent part of the resource definition ensures the new component
        # resource acts like anything else in the Pulumi ecosystem when being
        # called in code.
        self.automation_assets_bucket = VersionedBucket(
            f"{name}-automation-assets", opts=ResourceOptions(parent=self)
        )

        # Glue script setup
        config = Config("cape-cod")
        meta_config = config.require_object("meta")

        # NOTE: glue/etl config are not required like the meta config is...
        if meta_config.get("glue") and meta_config["glue"].get("etl"):
            for etl_def in meta_config["glue"]["etl"]:
                self.automation_assets_bucket.add_object(
                    etl_def["name"],
                    key=etl_def["key"],
                    # NOTE: These should always be file assets in the ETL case
                    source=FileAsset(etl_def["srcpth"]),
                )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs(
            {
                "{name}-automation_assets_bucket_name": self.automation_assets_bucket.bucket
            }
        )
