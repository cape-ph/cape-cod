"""Contains data lake related declaratiohs."""

import pulumi_aws as aws
from pulumi import AssetArchive, Config, FileAsset, Output, ResourceOptions

from capeinfra.iam import (
    get_inline_role,
    get_sqs_lambda_glue_trigger_policy,
    get_sqs_raw_notifier_policy,
)
from capeinfra.objectstorage import VersionedBucket
from capeinfra.pipeline.data import DataCrawler, EtlJob
from capeinfra.util.config import CapeConfig

from ..pulumi import CapeComponentResource


class DatalakeHouse(CapeComponentResource):
    """Top level object in the CAPE infrastructure for datalake storage."""

    def __init__(
        self,
        name: str,
        auto_assets_bucket: aws.s3.BucketV2,
        *args,
        config="datalakehouse",
        **kwargs,
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__(
            "capeinfra:datalake:DatalakeHouse",
            name,
            *args,
            config=config,
            **kwargs,
        )

        self.name = f"{name}"

        aws_config = Config("aws")
        self.aws_region = aws_config.require("region")

        # setup the data catalog and query engine to explore it
        self.configure_data_catalog()

        # setup the tributary ETL attributes database and all tributaries for
        # the lakehouse
        self.configure_tributaries(auto_assets_bucket)

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"datalakehouse_name": self.name})

    def configure_data_catalog(self):
        """Sets up the CAPE data catalog and the query engine for exploring it."""
        catalog_name = f"{self.name}-catalog"

        # create an object storage location for the metadata catalog to live in
        # NOTE: this object storage will change often and the concept of
        #       versions of the database doesn't really make sense. so
        #       this is not versioned object storage
        self.catalog_bucket = aws.s3.BucketV2(
            f"{catalog_name}-s3",
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} data catalog s3 bucket"},
        )

        # and the metadata catalog database itself
        self.catalog = CatalogDatabase(
            catalog_name,
            self.catalog_bucket,
            location=f"{catalog_name}-database",
            opts=ResourceOptions(parent=self),
            desc_name=f"{self.desc_name} data catalog database",
        )

        athena_prefix = f"{self.name}-athena"

        # like the catalog, athena results require an object storage location
        # NOTE: this object storage will change often and the concept of
        #       versions of the database doesn't really make sense. so
        #       this is not versioned object storage
        self.athena_results_bucket = aws.s3.BucketV2(
            f"{athena_prefix}-s3",
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} athena results s3 bucket"},
        )
        aws.athena.Workgroup(
            f"{athena_prefix}-wrkgrp",
            configuration=aws.athena.WorkgroupConfigurationArgs(
                enforce_workgroup_configuration=True,
                result_configuration=aws.athena.WorkgroupConfigurationResultConfigurationArgs(
                    output_location=self.athena_results_bucket.bucket.apply(
                        lambda b: f"s3://{b}/output"
                    )
                ),
            ),
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} athena workgroup"},
        )

    def configure_tributaries(
        self,
        auto_assets_bucket: aws.s3.BucketV2,
    ):
        """Sets up an ETL attributes database and the configured Tributaries.

        Args:
            auto_assets_bucket: The BucketV2 object for the automation assets
                                object storage.
        """
        # setup a DynamoDB table to hold the prefix/suffix/etl job attributes
        # for all tributaries. Each tributary will add its own configured ETL
        # attributes information to this table.
        self.etl_attr_ddb_table = aws.dynamodb.Table(
            f"{self.name}-etlattrs-ddb",
            name=f"{self.name}-ETLAttributes",
            # NOTE: this table will be accessed as needed to do ETL jobs.
            #       it'll be pretty hard (at least till this is use for a
            #       while) to come up with read/write metrics to set this table
            #       up as PROVISIONED with those values. We'd probably be much
            #       cheaper to go that route if we have a really solid idea of
            #       how many reads/writes this table needs
            billing_mode="PAY_PER_REQUEST",
            hash_key="bucket_name",
            range_key="prefix",
            attributes=[
                # NOTE: we do not need to define any part of the "schema" here
                #       that isn't needed in an index.
                # TODO: ISSUE #49
                {
                    "name": "bucket_name",
                    "type": "S",
                },
                {
                    "name": "prefix",
                    "type": "S",
                },
            ],
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} ETL attributes DynamoDB Table"
                ),
            },
        )

        # create the parts of the datalake from the tributary configuration
        # (e.g. hai, genomics, etc)
        self.tributaries = []
        for trib_config in self.config.get("tributaries", default=[]):
            trib_name = trib_config.get("name")
            self.tributaries.append(
                Tributary(
                    f"{self.name}-T-{trib_name}",
                    self.catalog.catalog_database,
                    auto_assets_bucket,
                    self.etl_attr_ddb_table,
                    self.aws_region,
                    config=trib_config,
                    opts=ResourceOptions(parent=self),
                    desc_name=f"{self.desc_name} {trib_name} tributary",
                )
            )


class CatalogDatabase(CapeComponentResource):
    """The metadata catalog for the datalake house."""

    def __init__(
        self,
        name: str,
        bucket: aws.s3.BucketV2,
        location="database",
        *args,
        **kwargs,
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__(
            "capeinfra:datalake:CatalogDatabase", name, *args, **kwargs
        )

        self.name = f"{name}"

        self.catalog_database = aws.glue.CatalogDatabase(
            self.name,
            location_uri=bucket.bucket.apply(lambda b: f"s3://{b}/{location}"),
            opts=ResourceOptions(parent=self),
            tags={"desc_name": self.desc_name or "AWS Glue Catalog Database"},
        )
        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs(
            {"catalog_database_name": self.catalog_database.name}
        )


class Tributary(CapeComponentResource):
    """Represents a single domain in the data lake.

    A tributary in the CAPE datalake sense is an encapsulation of:
      - an object storage location for raw data.
      - an object storage location for clean data.
      - a lambda job that kicks off when raw data lands. this may kick off lots
        of other things, but should result in *something* going into the clean
        object storage
      - one or more ETL jobs
      - any crawlers that should run when data hits raw/clean
    """

    RAW = "raw"
    CLEAN = "clean"

    def __init__(
        self,
        name: str,
        db: aws.glue.CatalogDatabase,
        auto_assets_bucket: aws.s3.BucketV2,
        etl_attrs_ddb_table: aws.dynamodb.Table,
        aws_region: str,
        *args,
        **kwargs,
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__("capeinfra:datalake:Tributary", name, *args, **kwargs)

        self.name = f"{name}"
        self.catalog = db
        self.aws_region = aws_region

        # configure the raw/clean buckets for the tributary. this will go down
        # into the crawlers for the buckets as well (IFF configured)
        self.buckets = {}
        for bucket_type in [Tributary.RAW, Tributary.CLEAN]:
            self.configure_bucket(bucket_type)

        # this queue is where all notifications of new objects added to the raw
        # bucket will go
        self.raw_data_queue = aws.sqs.Queue(
            # TODO: ISSUE #68
            f"{self.name}-rawq",
            name=f"{self.name}-rawq.fifo",
            content_based_deduplication=True,
            fifo_queue=True,
            tags={"desc_name": f"{self.desc_name} raw data notification queue"},
        )

        # setup all configured ETL jobs and add items to the DDB table for each.
        jobs = self.configure_etl(auto_assets_bucket, etl_attrs_ddb_table)

        # Lambda SQS Target setup
        self.configure_sqs_lambda_target(jobs)

        # Bucket notification setup
        self.configure_raw_bucket_notifications(etl_attrs_ddb_table)

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"tributary_name": self.name})

    def configure_bucket(self, bucket_type: str):
        """Creates/configures a raw or clean bucket based on config values.

        If a crawler is configured for the bucket, this will be added as well.

        Args:
            bucket_type: The type ('raw'/'clean') of the bucket being created.
            bucket_cfg: The config dict for te bucket, as specified in the
                        pulumi stack config.
        """
        bucket_config = self.config.get("buckets", bucket_type)
        bucket_name = bucket_config.get(
            "name", default=f"{self.name}-{bucket_type}-vbkt"
        )
        print(f"Bucket: {bucket_name}")
        self.buckets[bucket_type] = VersionedBucket(
            bucket_name,
            desc_name=f"{self.desc_name} {bucket_type}",
            opts=ResourceOptions(parent=self),
        )

        self.configure_crawler(
            bucket_name,
            self.buckets[bucket_type].bucket,
            bucket_type,
            bucket_config.get("crawler", default={}),
        )

    def configure_crawler(
        self,
        vbname: str,
        bucket: aws.s3.BucketV2,
        bucket_type: str,
        crawler_cfg: CapeConfig,
    ):
        """Creates/configures a crawler for a bucket based on config values.

        Args:
            vbname: The VersionedBucket name for the crawler to crawl.
            bucket: The bucket to be crawled.
            bucket_type: The type (e.g. raw, clean) of the bucket being crawled.
            crawler_cfg: The config dict for the crawler as specified in the
                         pulumi stack config.
        """
        if crawler_cfg:
            DataCrawler(
                f"{vbname}-crwl",
                bucket,
                self.catalog,
                opts=ResourceOptions(parent=self),
                desc_name=f"{self.desc_name} {bucket_type} data crawler",
                config=crawler_cfg,
            )

    def configure_etl(
        self,
        auto_assets_bucket: aws.s3.BucketV2,
        etl_attrs_ddb_table: aws.dynamodb.Table,
    ):
        """Configure all ETL jobs for the tributary.

        Args:
            etl_cfgs: The list of ETL configuration dicts from the pulumi config.
            auto_assets_bucket: The BucketV2 instance that contains the
                                automation assets.
            etl_attrs_ddb_table: A reference to the NOSQL table holding the ETL
                                 attributes.
        Returns:
            A list of configured EtlJobs.
        """

        jobs = []
        for cfg in self.config.get("pipelines", "data", "etl", default=[]):
            job = EtlJob(
                f"{self.name}-ETL-{cfg['name']}",
                self.buckets[Tributary.RAW].bucket,
                self.buckets[Tributary.CLEAN].bucket,
                auto_assets_bucket,
                opts=ResourceOptions(parent=self),
                desc_name=(f"{self.desc_name} raw to clean ETL job"),
                config=cfg,
            )

            jobs.append(job)

            # put the ETL job configuration into the tributary attributes table
            # for the raw bucket
            aws.dynamodb.TableItem(
                f"{self.name}-{job.config['name']}-ddbitem",
                table_name=etl_attrs_ddb_table.name,
                hash_key=etl_attrs_ddb_table.hash_key,
                range_key=etl_attrs_ddb_table.range_key.apply(
                    lambda rk: f"{rk}"
                ),
                item=Output.json_dumps(
                    {
                        "bucket_name": {
                            "S": self.buckets[Tributary.RAW].bucket.id,
                        },
                        "prefix": {"S": job.config["prefix"]},
                        "etl_job": {"S": job.job.id},
                        "suffixes": {
                            "L": [
                                {"S": suf}
                                for suf in job.config.get(
                                    "suffixes", default=[""]
                                )
                            ]
                        },
                    }
                ),
                opts=ResourceOptions(parent=self),
            )

        return jobs

    def configure_sqs_lambda_target(self, jobs: list):
        """Configures the Lmabda that will run on new SQS messages.

        Args:
            jobs: A list of configured EtlJobs that will be used by this Lambda.
        """
        # get a role for the raw bucket trigger
        self.sqs_trigger_role = get_inline_role(
            f"{self.name}-sqstrgrole",
            f"{self.desc_name} raw data SQS trigger role",
            "lmbd",
            "lambda.amazonaws.com",
            Output.all(
                qname=self.raw_data_queue.name,
                job_names=[j.job.name for j in jobs],
            ).apply(
                lambda args: get_sqs_lambda_glue_trigger_policy(
                    args["qname"], args["job_names"]
                )
            ),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        self.qmsg_handler = aws.lambda_.Function(
            f"{self.name}-sqslmbdtrgfnct",
            role=self.sqs_trigger_role.arn,
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/sqs_etl_job_trigger_lambda.py"
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
                    "QUEUE_NAME": self.raw_data_queue.name,
                }
            },
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": f"{self.desc_name} sqs message lambda trigger function"
            },
        )

        aws.lambda_.EventSourceMapping(
            f"{self.name}-sqslmbdatrgr",
            event_source_arn=self.raw_data_queue.arn,
            function_name=self.qmsg_handler.arn,
            function_response_types=["ReportBatchItemFailures"],
        )

    def configure_raw_bucket_notifications(
        self, etl_attrs_ddb_table: aws.dynamodb.Table
    ):
        """Configures notifications on the raw data bucket to invoke a function.

        Args:
            etl_attrs_ddb_table: The NOSQL table containing the ETL attributes
                                 for the data lake. The function being setup
                                 here will need to read from this table.
        """
        # get a role for the raw bucket trigger
        self.raw_bucket_trigger_role = get_inline_role(
            f"{self.name}-s3trgrole",
            f"{self.desc_name} raw data S3 bucket trigger role",
            "lmbd",
            "lambda.amazonaws.com",
            Output.all(
                qname=self.raw_data_queue.name,
                etl_attr_ddb_table_name=etl_attrs_ddb_table.name,
            ).apply(
                lambda args: get_sqs_raw_notifier_policy(
                    args["qname"], args["etl_attr_ddb_table_name"]
                )
            ),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        new_object_handler = aws.lambda_.Function(
            f"{self.name}-lmbdtrgfnct",
            role=self.raw_bucket_trigger_role.arn,
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/new_s3obj_queue_notifier_lambda.py"
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
                    "QUEUE_NAME": self.raw_data_queue.name,
                    "ETL_ATTRS_DDB_TABLE": etl_attrs_ddb_table.name,
                    "DDB_REGION": self.aws_region,
                }
            },
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": f"{self.desc_name} raw data lambda trigger function"
            },
        )

        # Give our function permission to invoke
        new_obj_handler_permission = aws.lambda_.Permission(
            f"{self.name}-rawS3-allow-lmbd",
            action="lambda:InvokeFunction",
            function=new_object_handler.arn,
            principal="s3.amazonaws.com",
            source_arn=self.buckets[Tributary.RAW].bucket.arn,
            opts=ResourceOptions(parent=self),
        )

        aws.s3.BucketNotification(
            f"{self.name}-raw-s3ntfn",
            bucket=self.buckets[Tributary.RAW].bucket.id,
            lambda_functions=[
                aws.s3.BucketNotificationLambdaFunctionArgs(
                    events=["s3:ObjectCreated:*"],
                    lambda_function_arn=new_object_handler.arn,
                )
            ],
            opts=ResourceOptions(
                depends_on=[new_obj_handler_permission], parent=self
            ),
        )
