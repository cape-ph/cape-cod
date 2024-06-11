"""Contains data lake related declaratiohs."""

import json

import pulumi_aws as aws
from pulumi import (
    AssetArchive,
    ComponentResource,
    Config,
    FileAsset,
    Output,
    ResourceOptions,
)

from ..objectstorage import VersionedBucket

CAPE_CSV_STANDARD_CLASSIFIER = "cape-csv-standard-classifier"

# TODO: fairly brittle. we need a way for the pulumi config to specify a string
#       and have it result in using a specific custom classifier. AWS adds some
#       extra characters to the name for uniqueness, so we can't just specify
#       the same name we put in the constructor for the classifier. so we need
#       a mapping of some sort.
CUSTOM_CLASSIFIERS = {
    CAPE_CSV_STANDARD_CLASSIFIER: aws.glue.Classifier(
        CAPE_CSV_STANDARD_CLASSIFIER,
        csv_classifier=aws.glue.ClassifierCsvClassifierArgs(
            serde="OpenCSVSerDe",
            delimiter=",",
            quote_symbol='"',
            contains_header="PRESENT",
        ),
    )
}

# TODO:
# - separate this out. didn't want to make a glue module as that's aws
#   specific, so figure out a more agnostic term (e.g. automation?) and use
#   that (then move the glue stuff into said module)
# - perms are hard coded rioght now. don't want that, but probs also doesn't
#   make sense to make those pulumi config items
# - need module for tributaries/lochs
#   - should be buildable with a config obj
#   - crawlers
#   - lambdas
# - need module to build the datalake
#   - catalog bucket/etc (needs to exist before tribs)
#   - all tributaries/lochs (based on config)
#   - athena results bucket
# - figure out where roles/perms fit in here


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

        config = Config("cape-cod")
        datalake_config = config.require_object("datalakehouse")

        catalog_name = f"{self.name}-catalog"

        # create an object storage location for the metadata catalog to live in
        # NOTE: this object storage will change often and the concept of
        #       versions of the database doesn't really make sense. so
        #       this is not versioned object storage
        self.catalog_bucket = aws.s3.BucketV2(
            f"{catalog_name}-bucket", opts=ResourceOptions(parent=self)
        )

        # and the metadata catalog database itself
        self.catalog = CatalogDatabase(
            catalog_name,
            self.catalog_bucket,
            location=f"{catalog_name}-database",
            opts=ResourceOptions(parent=self),
        )

        athena_prefix = f"{self.name}-athena"

        # like the catalog, athena results require an object storage location
        # NOTE: this object storage will change often and the concept of
        #       versions of the database doesn't really make sense. so
        #       this is not versioned object storage
        self.athena_results_bucket = aws.s3.BucketV2(
            f"{athena_prefix}-bucket", opts=ResourceOptions(parent=self)
        )
        aws.athena.Workgroup(
            f"{athena_prefix}-workgroup",
            configuration=aws.athena.WorkgroupConfigurationArgs(
                enforce_workgroup_configuration=True,
                result_configuration=aws.athena.WorkgroupConfigurationResultConfigurationArgs(
                    output_location=self.athena_results_bucket.bucket.apply(
                        lambda b: f"s3://{b}/output"
                    )
                ),
            ),
            opts=ResourceOptions(parent=self),
        )

        # create the parts of the datalake from the tributary configuration
        # (e.g. hai, genomics, etc)
        tributary_config = datalake_config.get("tributaries")
        self.tributaries = []
        if tributary_config:
            for trib_config in tributary_config:
                self.tributaries.append(
                    Tributary(
                        trib_config.get("name"),
                        trib_config,
                        self.catalog.catalog_database,
                        opts=ResourceOptions(parent=self),
                    )
                )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"datalakehouse_name": self.name})


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

    RAW = "raw"
    CLEAN = "clean"

    def __init__(
        self,
        name: str,
        cfg: dict,
        db: aws.glue.CatalogDatabase,
        opts=None,
    ):
        # By calling super(), we ensure any instantiation of this class
        # inherits from the ComponentResource class so we don't have to declare
        # all the same things all over again.
        super().__init__("capeinfra:datalake:Tributary", name, None, opts)

        self.name = f"{name}-tributary"
        self.catalog = db

        # configure the raw/clean buckets for the tributary. this will go down
        # into the crawlers for the buckets as well (IFF configured)
        self.buckets = {}
        buckets_cfg = cfg.get("buckets", {})
        for bucket_type in [Tributary.RAW, Tributary.CLEAN]:
            bucket_cfg = buckets_cfg.get(bucket_type, {})
            self.configure_bucket(bucket_type, bucket_cfg)

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"tributary_name": self.name})

    def configure_bucket(self, bucket_type: str, bucket_cfg: dict):
        """Creates/configures a raw or clean bucket based on config values.

        If a crawler is configured for the bucket, this will be added as well.

        Args:
            bucket_type: The type ('raw'/'clean') of the bucket being created.
            bucket_cfg: The config dict for te bucket, as specified in the
                        pulumi stack config.
        """
        bucket_name = bucket_cfg.get("name") or f"{self.name}-{bucket_type}-bucket"
        self.buckets[bucket_type] = VersionedBucket(
            bucket_name,
            opts=ResourceOptions(parent=self),
        )

        self.configure_crawler(
            bucket_name, self.buckets[bucket_type].bucket, bucket_cfg.get("crawler", {})
        )

    def configure_crawler(self, name: str, bucket: aws.s3.BucketV2, crawler_cfg: dict):
        """Creates/configures a crawler for a bucket based on config values.

        Args:
            name: The resource name for the crawler.
            bucket: The bucket to be crawled.
            crawler_cfg: The config dict for the crawler as specified in the
                         pulumi stack config.
        """
        if crawler_cfg:
            crawler = Crawler(
                name,
                bucket,
                self.catalog,
                classifiers=crawler_cfg.get("classifiers", []),
                opts=ResourceOptions(parent=self),
            )
            crawler.add_trigger_function()


class Crawler(ComponentResource):
    """A crawler for object storage."""

    def __init__(
        self,
        name: str,
        buckets: aws.s3.BucketV2 | list[aws.s3.BucketV2],
        db: aws.glue.CatalogDatabase,
        classifiers=None,
        opts=None,
    ):
        # By calling super(), we ensure any instantiation of this class
        # inherits from the ComponentResource class so we don't have to declare
        # all the same things all over again.
        super().__init__("capeinfra:datalake:Crawler", name, None, opts)

        self.name = f"{name}-crawler"
        self.buckets = buckets = buckets if isinstance(buckets, list) else [buckets]

        self.role = aws.iam.Role(
            f"{self.name}-role",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "glue.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
            opts=ResourceOptions(parent=self),
        )
        self.service_role = aws.iam.RolePolicyAttachment(
            f"{self.name}-service-role",
            role=self.role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole",
            opts=ResourceOptions(parent=self),
        )
        self.role_policy = aws.iam.RolePolicy(
            f"{name}-role-policy",
            role=self.role.id,
            policy=Output.all(
                buckets=[bucket.bucket for bucket in buckets], db=db.name
            ).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["s3:GetObject", "s3:ListBucket"],
                                "Resource": [
                                    f"arn:aws:s3:::{bucket}/*",
                                    f"arn:aws:s3:::{bucket}",
                                ],
                            }
                            for bucket in args["buckets"]
                        ],
                    }
                )
            ),
            opts=ResourceOptions(parent=self),
        )

        # if we have specified custom classifiers in the config, get the actual
        # names for them from our mapping.
        custom_classifiers = (
            [
                CUSTOM_CLASSIFIERS[c].name
                for c in classifiers
                if CUSTOM_CLASSIFIERS.get(c)
            ]
            if classifiers
            else []
        )

        self.crawler = aws.glue.Crawler(
            self.name,
            role=self.role.arn,
            database_name=db.name,
            s3_targets=[
                aws.glue.CrawlerS3TargetArgs(
                    path=bucket.bucket.apply(lambda b: f"s3://{b}/")
                )
                for bucket in buckets
            ],
            classifiers=custom_classifiers,
            opts=ResourceOptions(parent=self),
        )

        # We also need to register all the expected outputs for this component resource that will get returned by default.
        self.register_outputs({"crawler_name": self.crawler.name})

    def add_trigger_function(self):
        """Adds a trigger function for lambda to kick off the crawler."""

        crawler_trigger_role = aws.iam.Role(
            f"{self.name}-lambda-trigger-role",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
            opts=ResourceOptions(parent=self),
        )
        # Attach the Lambda service role for logging privileges
        aws.iam.RolePolicyAttachment(
            f"{self.name}-lambda-service-role-attachment",
            role=crawler_trigger_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )
        # Attach the Lambda service role for logging privileges
        aws.iam.RolePolicy(
            f"{self.name}-lambda-role-policy",
            role=crawler_trigger_role.id,
            policy=self.crawler.name.apply(
                lambda glue_crawler: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["glue:StartCrawler", "glue:GetCrawler"],
                                "Resource": [
                                    f"arn:aws:glue:*:*:crawler/{glue_crawler}"
                                ],
                            },
                        ],
                    }
                )
            ),
            opts=ResourceOptions(parent=self),
        )
        # Create our Lambda function that triggers the given glue job
        self.trigger_function = aws.lambda_.Function(
            f"{self.name}-lambda-function",
            role=crawler_trigger_role.arn,
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/lambda_glue_crawler_trigger.py"
                    )
                }
            ),
            runtime="python3.11",
            # in this case, the zip file for the lambda deployment is
            # being created by this code. and the zip file will be
            # called index. so the handler must be start with `index`
            # and the actual function in the script must be named
            # the same as the value here
            handler="index.index_handler",
            environment={
                "variables": {
                    "GLUE_CRAWLER_NAME": self.crawler.name,
                }
            },
        )
        # Give our function permission to invoke
        # Add a bucket notification to trugger our lambda automatically
        for bucket in self.buckets:
            crawler_function_permission = aws.lambda_.Permission(
                f"{self.name}-allow-lambda",
                action="lambda:InvokeFunction",
                function=self.trigger_function.arn,
                principal="s3.amazonaws.com",
                source_arn=bucket.arn,
            )
            aws.s3.BucketNotification(
                f"{self.name}-bucket-notification",
                bucket=bucket.id,
                lambda_functions=[
                    aws.s3.BucketNotificationLambdaFunctionArgs(
                        events=["s3:ObjectCreated:*"],
                        lambda_function_arn=self.trigger_function.arn,
                    )
                ],
                opts=ResourceOptions(depends_on=[crawler_function_permission]),
            )
