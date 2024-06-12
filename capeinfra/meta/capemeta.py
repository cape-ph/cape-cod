"""Contains resources used by the whole CAPE infra deployment."""

import pulumi_aws as aws
from pulumi import ComponentResource, Config, FileAsset, ResourceOptions

from ..objectstorage import VersionedBucket


class CapeMeta(ComponentResource):
    """Contains resources needed by all parts of the infra."""

    def __init__(self, name, opts=None):
        # This maintains parental relationships within the pulumi stack
        super().__init__("capeinfra:meta:capemeta:CapeMeta", name, None, opts)

        self.automation_assets_bucket = VersionedBucket(
            f"{name}-automation-assets", opts=ResourceOptions(parent=self)
        )

        # Setup for the glue script assets
        config = Config("cape-cod")
        meta_config = config.require_object("meta")

        # NOTE: glue/etl config are not required like the meta config is...
        if meta_config.get("glue") and meta_config["glue"].get("etl"):
            for etl_def in meta_config["glue"]["etl"]:
                self.automation_assets_bucket.add_object(
                    etl_def["name"],
                    key=etl_def["key"],
                    # NOTE: These should always be file assets in the ETL case
                    #       (as opposed to archive assets)
                    source=FileAsset(etl_def["srcpth"]),
                )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs(
            {"cape-meta-automation-assets-bucket": self.automation_assets_bucket.bucket}
        )
