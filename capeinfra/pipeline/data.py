"""Abstractions for data pipelines."""

from copy import deepcopy

import pulumi_aws as aws
from pulumi import AssetArchive, FileAsset, Output, ResourceOptions

import capeinfra
from capeinfra.iam import (
    get_bucket_reader_policy,
    get_etl_job_s3_policy,
    get_inline_role,
    get_start_crawler_policy,
    get_start_etl_job_policy,
)
from capepulumi import CapeComponentResource

CAPE_CSV_STANDARD_CLASSIFIER = "cape-csv-standard-classifier"

# TODO: ISSUE #8
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


class DataCrawler(CapeComponentResource):
    """A crawler for object storage."""

    @property
    def default_config(self):
        return {
            # a cron formatted schedule string for the crawler's periodicity.
            # The default is 0200 daily (so as to not rack up charges)
            # NOTE: this cannot be faster than every 5
            # minutes. see here for more:
            # https://docs.aws.amazon.com/glue/latest/dg/monitor-data-warehouse-schedule.html
            "schedule": "0 2 * * ? *",
            # A list of custom classifiers for the crawler, if any.
            "classifiers": [],
            # a list of exclude paths for the crawler. see here for more:
            # https://docs.aws.amazon.com/glue/latest/dg/define-crawler.html#define-crawler-choose-data-sources
            # NOTE: at this time, all given exclusions apply to all buckets the
            # crawler is set up for.
            "excludes": [],
        }

    def __init__(
        self,
        name: str,
        buckets: aws.s3.BucketV2 | list[aws.s3.BucketV2],
        db: aws.glue.CatalogDatabase,
        *args,
        prefix: str | None = None,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the resource.
            buckets: One or more buckets (a list of them if more than one) that
                     the crawler will crawl.
            prefix: A prefix string within a bucket to crawl which limits the
                    content that will be indexed by the crawler.
            db: The catalog database where the crawler will write metadata.
            opts: The ResourceOptions to apply to the crawler resource.
        Returns:
        """
        # This maintains parental relationships within the pulumi stack
        super().__init__("capeinfra:datalake:Crawler", name, *args, **kwargs)

        self.name = f"{name}"
        self.buckets = buckets = (
            buckets if isinstance(buckets, list) else [buckets]
        )

        # get a role for the crawler
        self.crawler_role = get_inline_role(
            self.name,
            f"{self.desc_name} data crawler role",
            "",
            "glue.amazonaws.com",
            Output.all(
                buckets=[bucket.bucket for bucket in self.buckets],
                db=db.name,
            ).apply(lambda args: get_bucket_reader_policy(args["buckets"])),
            "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole",
            opts=ResourceOptions(parent=self),
        )

        # if we have specified custom classifiers in the config, get the actual
        # names for them from our mapping.
        custom_classifiers = [
            CUSTOM_CLASSIFIERS[c].name
            for c in self.config.get("classifiers", default=[])
            if CUSTOM_CLASSIFIERS.get(c)
        ]

        self.crawler = aws.glue.Crawler(
            f"{self.name}-gcrwl",
            role=self.crawler_role.arn,
            database_name=db.name,
            s3_targets=[
                aws.glue.CrawlerS3TargetArgs(
                    path=bucket.bucket.apply(
                        lambda b: f"s3://{b}/{prefix+'/' if prefix else ''}"
                    ),
                    exclusions=self.config["excludes"],
                )
                for bucket in buckets
            ],
            classifiers=custom_classifiers,
            schedule=f"cron({self.config['schedule']})",
            opts=ResourceOptions(parent=self),
            tags={"desc_name": self.desc_name or "AWS Glue Data Crawler"},
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"crawler_name": self.crawler.name})

    def add_trigger_function(self):
        """Adds a trigger function for lambda to kick off the crawler.

        NOTE: We currently only support scheduled crawlers. The trigger
              function way of doing things works, but we have no way to
              configure switching between the 2. This code is left here cause
              it's a useful way to kick off crawlers in some cases.
        """

        # get a role for the crawler trigger function
        self.trigger_role = get_inline_role(
            f"{self.name}-trgrole",
            f"{self.desc_name} data crawler trigger role",
            "lmbd",
            "lambda.amazonaws.com",
            self.crawler.name.apply(
                lambda glue_crawler: get_start_crawler_policy(glue_crawler)
            ),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        self.trigger_function = aws.lambda_.Function(
            f"{self.name}-lmbdfnct",
            role=self.trigger_role.arn,
            layers=[capeinfra.meta.capepy.lambda_layer.arn],
            # NOTE: Lambdas want a zip file as opposed to an s3 script location
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/lambda_glue_crawler_trigger.py"
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
                    "GLUE_CRAWLER_NAME": self.crawler.name,
                }
            },
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} lambda trigger function"},
        )
        # Give our function permission to invoke
        # Add a bucket notification to trugger our lambda automatically
        for bucket in self.buckets:
            crawler_function_permission = aws.lambda_.Permission(
                f"{self.name}-allow-lmbd",
                action="lambda:InvokeFunction",
                function=self.trigger_function.arn,
                principal="s3.amazonaws.com",
                source_arn=bucket.arn,
                opts=ResourceOptions(parent=self),
            )

            aws.s3.BucketNotification(
                f"{self.name}-s3ntfn",
                bucket=bucket.id,
                lambda_functions=[
                    aws.s3.BucketNotificationLambdaFunctionArgs(
                        events=["s3:ObjectCreated:*"],
                        lambda_function_arn=self.trigger_function.arn,
                    )
                ],
                opts=ResourceOptions(
                    depends_on=[crawler_function_permission], parent=self
                ),
            )


class EtlJob(CapeComponentResource):
    """An extract/transform/load job."""

    @property
    def default_config(self):
        return {
            "max_concurrent_runs": 5,
        }

    def __init__(
        self,
        name: str,
        raw_bucket: aws.s3.BucketV2,
        clean_bucket: aws.s3.BucketV2,
        script_bucket: aws.s3.BucketV2,
        *args,
        default_args: dict = {},
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the resource.
            raw_bucket: The raw object storage location the ETL job will use as
                        its source.
            clean_bucket: The clean object storage location the ETL job will
                          use as the sink for the output of transform.
            script_bucket: The object storage location where etl scripts are
                           kept.
            default_args: default arguments for this ETL job if any.
            opts: The ResourceOptions to apply to the crawler resource.
        Returns:
        """
        # This maintains parental relationships within the pulumi stack
        super().__init__("capeinfra:datalake:Job", name, *args, **kwargs)

        self.name = f"{name}"
        self.raw_bucket = raw_bucket
        self.clean_bucket = clean_bucket

        self.etl_role = get_inline_role(
            self.name,
            f"{self.desc_name} ETL job role",
            "",
            "glue.amazonaws.com",
            Output.all(
                raw_bucket=raw_bucket.bucket,
                clean_bucket=clean_bucket.bucket,
                script_bucket=script_bucket.bucket,
                assets_bucket=capeinfra.meta.automation_assets_bucket.bucket.bucket,
            ).apply(
                lambda args: get_etl_job_s3_policy(
                    args["raw_bucket"],
                    args["clean_bucket"],
                    args["script_bucket"],
                    self.config["script"],
                    args["assets_bucket"],
                )
            ),
            srvc_policy_attach=None,
            opts=ResourceOptions(parent=self),
        )

        default_args = deepcopy(default_args)
        if (
            "pymodules" in self.config
            and "--additional-python-modules" not in default_args
        ):
            default_args["--additional-python-modules"] = ",".join(
                self.config["pymodules"]
            )

        default_args["--CLEAN_BUCKET_NAME"] = self.clean_bucket.bucket

        # FIXME: FIGURE OUT HOW TO DEAL WITH OUTPUT[str] WITH ADDITIONAL PYTHON
        # MODULES, CURRENTLY BREAKS THE INSTALLATION OF THE WHEEL
        def add_to_python_modules(capepy):
            default_args["--additional-python-modules"] = (
                f"{default_args['--additional-python-modules']},{capepy}"
                if "--additional-python-modules" in default_args
                else capepy
            )
            return default_args

        self.job = aws.glue.Job(
            self.name,
            role_arn=self.etl_role.arn,
            command=aws.glue.JobCommandArgs(
                script_location=script_bucket.bucket.apply(
                    lambda b: f"s3://{b}/{self.config['script']}"
                ),
                python_version="3",
            ),
            default_arguments=capeinfra.meta.capepy.uri.apply(
                add_to_python_modules
            ),
            execution_property=aws.glue.JobExecutionPropertyArgs(
                max_concurrent_runs=self.config.get("max_concurrent_runs"),
            ),
            opts=ResourceOptions(parent=self),
            tags={"desc_name": self.desc_name or "AWS Glue ETL Job"},
        )
        self.register_outputs({"job_name": self.job.name})

    def add_trigger_function(self):
        """Adds a trigger function to kick off this job.

        Returns:
            A tuple containing the lambda function resource that will trigger
            this job and the lambda permission the function will execute with.
        """
        # get a role for the etl job trigger
        self.trigger_role = get_inline_role(
            f"{self.name}-trgrole",
            f"{self.desc_name} ETL job trigger role",
            "lmbd",
            "lambda.amazonaws.com",
            self.job.name.apply(
                lambda glue_job: get_start_etl_job_policy(glue_job)
            ),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        etl_function = aws.lambda_.Function(
            f"{self.name}-lmbdtrgfnct",
            role=self.trigger_role.arn,
            layers=[capeinfra.meta.capepy.lambda_layer.arn],
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/hai_lambda_glue_trigger.py"
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
                    "GLUE_JOB_NAME": self.job.name,
                    "RAW_BUCKET_NAME": self.raw_bucket.bucket,
                }
            },
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} lambda trigger function"},
        )

        # Give our function permission to invoke
        etl_permission = aws.lambda_.Permission(
            f"{self.name}-allow-lmbd",
            action="lambda:InvokeFunction",
            function=etl_function.arn,
            principal="s3.amazonaws.com",
            source_arn=self.raw_bucket.arn,
            opts=ResourceOptions(parent=self),
        )

        return etl_function, etl_permission
