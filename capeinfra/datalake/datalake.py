"""Contains data lake related declarations."""

from typing import List, Literal

import pulumi_aws as aws
from pulumi import AssetArchive, Config, FileAsset, Output, ResourceOptions, log

import capeinfra
from capeinfra.iam import add_resources, aggregate_statements, get_inline_role
from capeinfra.meta.capemeta import CapeMeta
from capeinfra.pipeline.data import DataCrawler, EtlJob
from capeinfra.resources.database import DynamoTable
from capeinfra.resources.objectstorage import Bucket, VersionedBucket
from capeinfra.resources.queue import SQSQueue
from capepulumi import CapeComponentResource

# aliases for prefixes and suffixes we expect for tributary buckets that have an
# etl associated
TributaryETLBucketIdPrefixes = Literal["input", "result"]
TributaryETLBucketIdSuffixes = Literal["clean", "raw"]


class DatalakeHouse(CapeComponentResource):
    """Top level object in the CAPE infrastructure for datalake storage."""

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:datalake:DatalakeHouse"

    def __init__(
        self,
        name: str,
        *args,
        **kwargs,
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, config="datalakehouse", **kwargs)

        self.name = f"{name}"

        aws_config = Config("aws")
        self.aws_region = aws_config.require("region")

        # setup the data catalog and query engine to explore it
        self.configure_data_catalog()

        # setup the tributary ETL attributes database and all tributaries for
        # the lakehouse
        self.configure_tributaries()

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
        self.catalog_bucket = Bucket(
            f"{catalog_name}-s3",
            desc_name=f"{self.desc_name} data catalog",
            opts=ResourceOptions(parent=self),
        )

        athena_prefix = f"{self.name}-athena"

        # like the catalog, athena results require an object storage location
        # NOTE: this object storage will change often and the concept of
        #       versions of the database doesn't really make sense. so
        #       this is not versioned object storage
        self.athena_results_bucket = Bucket(
            f"{athena_prefix}-s3",
            opts=ResourceOptions(parent=self),
            desc_name=f"{self.desc_name} athena results",
        )
        aws.athena.Workgroup(
            f"{athena_prefix}-wrkgrp",
            configuration=aws.athena.WorkgroupConfigurationArgs(
                enforce_workgroup_configuration=True,
                result_configuration=aws.athena.WorkgroupConfigurationResultConfigurationArgs(
                    output_location=self.athena_results_bucket.bucket.bucket.apply(
                        lambda b: f"s3://{b}/output"
                    )
                ),
            ),
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} athena workgroup"},
        )

    def configure_tributaries(
        self,
    ):
        """Sets up an ETL attributes database and the configured Tributaries."""
        # setup a DynamoDB table to hold the prefix/suffix/etl job attributes
        # for all tributaries. Each tributary will add its own configured ETL
        # attributes information to this table.

        self.etl_attr_ddb_table = DynamoTable(
            name=f"{self.name}-ETLAttrs",
            hash_key="bucket_name",
            range_key="prefix",
            idx_attrs=[
                # NOTE: we do not need to define any part of the "schema" here
                #       that isn't needed in an index.
                # TODO: ISSUE #49
                {"name": "bucket_name", "type": "S"},
                {"name": "prefix", "type": "S"},
            ],
            desc_name=(f"{self.desc_name} ETL attributes DynamoDB Table"),
        )

        self.crawler_attrs_ddb_table = DynamoTable(
            name=f"{self.name}-CrawlerAttrs",
            hash_key="bucket_name",
            idx_attrs=[
                # NOTE: we do not need to define any part of the "schema" here
                #       that isn't needed in an index.
                # TODO: ISSUE #49
                {"name": "bucket_name", "type": "S"},
            ],
            opts=ResourceOptions(parent=self),
            desc_name=(
                f"{self.desc_name} Glue Crawler attributes DynamoDB Table"
            ),
        )

        # create the parts of the datalake from the tributary configuration
        # (e.g. hai, genomics, etc)
        self.tributaries = []
        for trib_config in self.config.get("tributaries", default=[]):
            trib_name = trib_config.get("name")

            self.tributaries.append(
                Tributary(
                    f"{self.name}-T-{trib_name}",
                    self.catalog_bucket,
                    self.etl_attr_ddb_table,
                    self.crawler_attrs_ddb_table,
                    self.aws_region,
                    config=trib_config,
                    # TODO: much like passing around lambda function layers
                    #       (which generally exist in capemeta but are needed
                    #       elsewhere), we need a different way to pass the
                    #       cors_policies around (or make a registry to fetch
                    #       them from). We also want the tributary configuration
                    #       to be able to add to/override named cors config in
                    #       their own scopes, so when we attack that it would
                    #       make sense to look into how to make accessing them
                    #       better.
                    cors_policies=(
                        self.config.get("bucket_cors_policies", default=None)
                    ),
                    opts=ResourceOptions(parent=self),
                    desc_name=f"{self.desc_name} {trib_name} tributary",
                )
            )


class CatalogDatabase(CapeComponentResource):
    """The metadata catalog for the datalake house."""

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:datalake:CatalogDatabase"

    def __init__(
        self,
        name: str,
        bucket: Bucket,
        location="database",
        *args,
        **kwargs,
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)

        self.name = f"{name}"

        self.catalog_database = aws.glue.CatalogDatabase(
            self.name,
            location_uri=bucket.bucket.bucket.apply(
                lambda b: f"s3://{b}/{location}"
            ),
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
      - a collection of buckets for storing objects which can be source and sink
        locations for data pipelines.
      - a lambda job that kicks off when data lands in a source location. this
        may kick off lots of other things, but should result in *something* going
        into a sink object storage
      - one or more ETL jobs
      - any crawlers that should run when data hits a bucket
    """

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:datalake:Tributary"

    def __init__(
        self,
        name: str,
        catalog_bucket: Bucket,
        etl_attrs_ddb_table: DynamoTable,
        crawler_attrs_ddb_table: DynamoTable,
        aws_region: str,
        *args,
        # TODO: much like passing around lambda function layers
        #       (which generally exist in capemeta but are needed
        #       elsewhere), we need a different way to pass the
        #       cors_policies around (or make a registry to fetch
        #       them from). We also want the tributary configuration
        #       to be able to add to/override named cors config in
        #       their own scopes, so when we attack that it would
        #       make sense to look into how to make accessing them
        #       better.
        cors_policies: dict | None = None,
        **kwargs,
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)

        self.name = f"{name}"
        catalog_name = f"{self.name}-catalog"
        self.catalog = CatalogDatabase(
            catalog_name,
            catalog_bucket,
            location=f"{catalog_name}-database",
            opts=ResourceOptions(parent=self),
            desc_name=f"{self.desc_name} data catalog database",
        )
        self.aws_region = aws_region
        self.cors_policies = cors_policies

        # configure the buckets for the tributary. this will go down
        # into the crawlers for the buckets as well (IFF configured)
        self.buckets = dict[str, VersionedBucket]()
        self.crawlers = dict[str, DataCrawler]()
        for bucket_id in self.config.get("buckets", default={}):
            self.configure_bucket(bucket_id, crawler_attrs_ddb_table)

        # when new objects are put into `self.buckets` targets, a trigger
        # function will put messages in this queue for processing down the line
        self.src_data_queue = SQSQueue(name=f"{self.name}-srcq")

        self.sources = set()

        # setup all configured ETL jobs and add items to the DDB table for each.
        jobs = self.configure_etl(etl_attrs_ddb_table)

        # Lambda SQS Target setup
        self.configure_sqs_lambda_target(jobs)

        # Bucket notification setup
        self.configure_src_bucket_notifications(etl_attrs_ddb_table)

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"tributary_name": self.name})

    def filter_buckets(
        self,
        prefix: (
            List[TributaryETLBucketIdPrefixes] | TributaryETLBucketIdPrefixes
        ) = ["input", "result"],
        suffix: (
            List[TributaryETLBucketIdSuffixes] | TributaryETLBucketIdSuffixes
        ) = ["clean", "raw"],
    ) -> list[VersionedBucket]:
        """Return a subset of tributary buckets base on bucket id parts.

        This is intended for use to get [input|result]-[raw|clean] bucket sets.
        There is currently no rule that says there must be buckets with those
        names in a tributary, but this method operates on only those values.

        Args:
            prefix: A bucket id prefix or list of prefixes to filter based on.
            suffix: A bucket id suffix or list of suffixes to filter based on.

        Returns:
            A list of VersionedBuckets in the tributary matching the filters.
        """
        prefix = prefix if isinstance(prefix, list) else [prefix]
        suffix = suffix if isinstance(suffix, list) else [suffix]

        filtered_buckets = list[VersionedBucket]()

        for bid, vb in self.buckets.items():
            bid_parts = bid.split("-")
            if len(bid_parts) != 2:
                # if we don't have 2 parts here, the bucket name is not of the
                # format we want to filter against
                continue
            if bid_parts[0] in prefix and bid_parts[1] in suffix:
                filtered_buckets.append(vb)

        return filtered_buckets

    def configure_bucket(
        self, bucket_id: str, crawler_attrs_ddb_table: DynamoTable
    ):
        """Creates/configures a bucket based on config values.

        If a crawler is configured for the bucket, this will be added as well.

        Args:
            bucket_id: The id of the bucket being created.
            crawler_attrs_ddb_table: A DynamoTable that holds the attributes of
                                     the crawlers available for the bucket being
                                     configured.
        """
        bucket_config = self.config.get("buckets", bucket_id)
        bucket_name = bucket_config.get(
            "name", default=f"{self.name}-{bucket_id}-vbkt"
        )

        # deal with cors policy if we have one named in the bucket config *and*
        # we have a top level definition matching the name
        cors_policy_names = bucket_config.get("cors_policies", default=None)
        cors_rules = None

        if self.cors_policies is None:
            if cors_policy_names is not None:
                msg = (
                    f"Tributary {self.name} bucket {bucket_name} specifies cors "
                    f"policies ({cors_policy_names}) that do not match any "
                    f"specified in the data lake configuration."
                )
                log.error(msg)
                raise ValueError(msg)
        else:
            if cors_policy_names is not None:
                cors_rules = [
                    self.cors_policies.get(n) for n in cors_policy_names
                ]
                if None in cors_rules:
                    msg = (
                        f"Tributary {self.name} bucket {bucket_name} specifies cors "
                        f"policies ({cors_policy_names}) that do not match any "
                        f"specified in the data lake configuration."
                    )
                    log.error(msg)
                    raise ValueError(msg)

        self.buckets[bucket_id] = VersionedBucket(
            bucket_name,
            cors_rules=cors_rules,
            desc_name=f"{self.desc_name} {bucket_id}",
            opts=ResourceOptions(parent=self),
        )

        crawler_config = bucket_config.get("crawler")
        if crawler_config:
            self.crawlers[bucket_id] = DataCrawler(
                f"{bucket_name}-crwl",
                self.buckets[bucket_id],
                self.catalog.catalog_database,
                opts=ResourceOptions(parent=self),
                desc_name=f"{self.desc_name} {bucket_id} data crawler",
                config=crawler_config,
            )

            crawler_attrs_ddb_table.add_table_item(
                f"{self.name}-{bucket_id}-crawler-ddbitem",
                item={
                    "bucket_name": {"S": self.buckets[bucket_id].bucket.id},
                    "crawler_name": {
                        "S": self.crawlers[bucket_id].crawler.name
                    },
                },
            )

    def configure_etl(self, etl_attrs_ddb_table: DynamoTable):
        """Configure all ETL jobs for the tributary.

        Args:
            etl_cfgs: The list of ETL configuration dicts from the pulumi config.
            etl_attrs_ddb_table: The DynamoTable holding the ETL attributes.
        Returns:
            A list of configured EtlJobs.
        """

        jobs = []
        for cfg in self.config.get("pipelines", "data", "etl", default=[]):
            job = EtlJob(
                f"{self.name}-ETL-{cfg['name']}",
                self.buckets[cfg["src"]],
                self.buckets[cfg["sink"]],
                capeinfra.meta.automation_assets_bucket,
                opts=ResourceOptions(parent=self),
                desc_name=(f"{self.desc_name} {cfg['name']} ETL job"),
                config=cfg,
            )

            jobs.append(job)

            # put the ETL job configuration into the tributary attributes table
            # for the source bucket
            etl_attrs_ddb_table.add_table_item(
                f"{self.name}-{job.config['name']}",
                item={
                    "bucket_name": {
                        "S": self.buckets[cfg["src"]].bucket.id,
                    },
                    "prefix": {"S": job.config["prefix"]},
                    "etl_job": {"S": job.job.id},
                    "sink_bucket_name": {
                        "S": self.buckets[cfg["sink"]].bucket.id
                    },
                    "suffixes": {
                        "L": [
                            {"S": suf}
                            for suf in job.config.get("suffixes", default=[""])
                        ]
                    },
                },
            )
            self.sources.add(cfg["src"])

        return jobs

    def configure_sqs_lambda_target(self, jobs: list):
        """Configures the Lambda that will run on new SQS messages.

        Args:
            jobs: A list of configured EtlJobs that will be used by this Lambda.
        """
        # we should always have at least one job at this point, and all jobs
        # have the same policy set, so just grab the run_job policy of the first
        run_job_policy = jobs[0].policies[EtlJob.PolicyEnum.run_job]

        # get a role for the source bucket triggers
        self.sqs_trigger_role = get_inline_role(
            f"{self.name}-sqstrgrole",
            f"{self.desc_name} source data SQS trigger role",
            "lmbd",
            "lambda.amazonaws.com",
            aggregate_statements(
                [capeinfra.meta.policies[CapeMeta.PolicyEnum.logging]]
                + [
                    self.src_data_queue.sqs_queue.arn.apply(
                        lambda arn: add_resources(
                            self.src_data_queue.policies[
                                SQSQueue.PolicyEnum.consume_msg
                            ],
                            arn,
                        )
                    )
                ]
                + [
                    Output.all(job_arns=[j.job.arn for j in jobs]).apply(
                        lambda args: add_resources(
                            run_job_policy,
                            *args["job_arns"],
                        )
                    )
                ]
            ),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        self.qmsg_handler = aws.lambda_.Function(
            f"{self.name}-sqslmbdtrgfnct",
            role=self.sqs_trigger_role.arn,
            layers=[capeinfra.meta.capepy.lambda_layer.arn],
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/trigger-functions/sqs/sqs_etl_job_trigger_lambda.py"
                    )
                }
            ),
            runtime="python3.10",
            # in this case, the zip file for the lambda deployment is
            # being created by this code. and the zip file will be
            # called index. so the handler must be start with `index`
            # and the actual function in the script must be named
            # the same as the value here
            handler="index.index_handler",
            environment={
                "variables": {
                    "QUEUE_NAME": self.src_data_queue.name,
                }
            },
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": f"{self.desc_name} sqs message lambda trigger function"
            },
        )

        aws.lambda_.EventSourceMapping(
            f"{self.name}-sqslmbdatrgr",
            event_source_arn=self.src_data_queue.sqs_queue.arn,
            function_name=self.qmsg_handler.arn,
            function_response_types=["ReportBatchItemFailures"],
        )

    def configure_src_bucket_notifications(
        self, etl_attrs_ddb_table: DynamoTable
    ):
        """Configures notifications on the source data buckets to invoke a function.

        Args:
            etl_attrs_ddb_table: The NOSQL table containing the ETL attributes
                                 for the data lake. The function being setup
                                 here will need to read from this table.
        """

        # get a role for the source bucket trigger
        self.src_bucket_trigger_role = get_inline_role(
            f"{self.name}-s3trgrole",
            f"{self.desc_name} source data S3 bucket trigger role",
            "lmbd",
            "lambda.amazonaws.com",
            aggregate_statements(
                [capeinfra.meta.policies[CapeMeta.PolicyEnum.logging]]
                + [
                    self.src_data_queue.sqs_queue.arn.apply(
                        lambda arn: add_resources(
                            self.src_data_queue.policies[
                                SQSQueue.PolicyEnum.put_msg
                            ],
                            arn,
                        )
                    )
                ]
                + [
                    etl_attrs_ddb_table.ddb_table.arn.apply(
                        lambda arn: add_resources(
                            etl_attrs_ddb_table.policies[
                                DynamoTable.PolicyEnum.read
                            ],
                            arn,
                        )
                    )
                ]
            ),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        new_object_handler = aws.lambda_.Function(
            f"{self.name}-lmbdtrgfnct",
            role=self.src_bucket_trigger_role.arn,
            layers=[capeinfra.meta.capepy.lambda_layer.arn],
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/trigger-functions/s3/new_s3obj_queue_notifier_lambda.py"
                    )
                }
            ),
            runtime="python3.10",
            # in this case, the zip file for the lambda deployment is
            # being created by this code. and the zip file will be
            # called index. so the handler must be start with `index`
            # and the actual function in the script must be named
            # the same as the value here
            handler="index.index_handler",
            environment={
                "variables": {
                    "QUEUE_NAME": self.src_data_queue.sqs_queue.name,
                    "ETL_ATTRS_DDB_TABLE": etl_attrs_ddb_table.name,
                    "DDB_REGION": self.aws_region,
                }
            },
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": f"{self.desc_name} source data lambda trigger function"
            },
        )

        # Give our function permission to invoke
        for src in self.sources:
            new_obj_handler_permission = aws.lambda_.Permission(
                f"{self.name}-{src}-allow-lmbd",
                action="lambda:InvokeFunction",
                function=new_object_handler.arn,
                principal="s3.amazonaws.com",
                source_arn=self.buckets[src].bucket.arn,
                opts=ResourceOptions(parent=self),
            )

            aws.s3.BucketNotification(
                f"{self.name}-{src}-s3ntfn",
                bucket=self.buckets[src].bucket.id,
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
