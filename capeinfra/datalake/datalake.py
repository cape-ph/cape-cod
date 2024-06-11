"""Contains data lake related declaratiohs."""

import pulumi_aws as aws
from pulumi import ComponentResource, Output, ResourceOptions

# TODO:
# - need module for tributaries/lochs
#   - should be buildable with a config obj
#   - crawlers
#   - lambdas
# - need module to build the datalake
#   - catalog bucket/etc (needs to exist before tribs)
#   - all tributaries/lochs (based on config)
#   - athena results bucket
# - figure out where roles/perms fit in here
# - make issue for sns queue instead of notifications
# - make issue for fixing up assets in this repo (should come from elsewhere)


class DatalakeHouse(ComponentResource):
    """Top level object in the CAPE infrastructure for data storage."""

    def __init__(
        self,
        name: str,
        opts=None,
    ):
        # By calling super(), we ensure any instantiation of this class
        # inherits from the ComponentResource class so we don't have to declare
        # all the same things all over again.
        super().__init__("capeinfra:datalake:DatalakeHouse", name, None, opts)

        self.name = f"{name}"

        catalog_name = f"{self.name}-catalog"

        # first we need to create an object storage location for the metadata
        # catalog to live in
        # NOTE: this object storage will change often and the concept of
        #       versions of the database doesn't really make sense. so
        #       this is not versioned object storage
        self.catalog_bucket = aws.s3.BucketV2(
            f"{catalog_name}-bucket", opts=ResourceOptions(parent=self)
        )

        # next we need to create the metadata catalog database
        self.catalog = CatalogDatabase(
            catalog_name,
            self.catalog_bucket,
            location=f"{catalog_name}-database",
        )

        # TODO: fill in the constituent parts of the lakehouse and register
        #       self as their parent

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"datalakehouse_name": self.name})


class Tributary(ComponentResource):
    """Represents a single domain in the data lake.

    A tributary in the CAPE data lake sense is an encapsulation of:
      - an object storage location for raw data.
      - an object storage location for clean data.
      - a lambda job that kicks off when raw data lands. this may kick off lots
        of other things, but should result in *something* going into the clean
        object storage
      - any crawlers that should run when data hits raw/clean
      - TBD MORE
    """

    def __init__(
        self,
        name: str,
        opts=None,
    ):
        # By calling super(), we ensure any instantiation of this class
        # inherits from the ComponentResource class so we don't have to declare
        # all the same things all over again.
        super().__init__("capeinfra:datalake:Tributary", name, None, opts)

        self.name = f"{name}-tributary"

        # TODO: fill in the constituent parts of the tributary and register
        #       self as their parent

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"tributary_name": self.name})


class CatalogDatabase(ComponentResource):
    """The metadata catalog for the datalake house."""

    def __init__(
        self,
        name: str,
        bucket: aws.s3.BucketV2,
        location="database",
        opts=None,
    ):
        # By calling super(), we ensure any instantiation of this class
        # inherits from the ComponentResource class so we don't have to declare
        # all the same things all over again.
        # TODO: Decide on our replacement for `pkg:index` here.
        super().__init__("capeinfra:datalake:CatalogDatabase", name, None, opts)

        self.name = f"{name}"

        # The parent part of the resource definition ensures the new component
        # resource acts like anything else in the Pulumi ecosystem when being
        # called in code.
        self.catalog_database = aws.glue.CatalogDatabase(
            self.name,
            location_uri=bucket.bucket.apply(lambda b: f"s3://{b}/{location}"),
            opts=ResourceOptions(parent=self),
        )
        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"catalog_database_name": self.catalog_database.name})
