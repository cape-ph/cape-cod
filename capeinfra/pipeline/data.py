"""Abstractions for data pipelines."""

import pulumi_aws as aws
from pulumi import AssetArchive, FileAsset, Output, ResourceOptions

from ..iam import (
    get_bucket_reader_policy,
    get_etl_job_s3_policy,
    get_service_assume_role,
    get_start_etl_job_policy,
)
from ..pulumi import DescribedComponentResource, ObjectStorageTriggerable

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


class DataCrawler(ObjectStorageTriggerable):
    """A triggerable crawler for object storage."""

    def __init__(
        self,
        name: str,
        buckets: aws.s3.BucketV2 | list[aws.s3.BucketV2],
        db: aws.glue.CatalogDatabase,
        *args,
        classifiers=None,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the resource.
            buckets: One or more buckets (a list of them if more than one) that
                     the crawler will crawl.
            db: The catalog database where the crawler will write metadata.
            classifiers: A list of custom classifiers for the crawler, if any.
            opts: The ResourceOptions to apply to the crawler resource.
        Returns:
        """
        # This maintains parental relationships within the pulumi stack
        super().__init__("capeinfra:datalake:Crawler", name, *args, **kwargs)

        self.buckets = buckets if isinstance(buckets, list) else [buckets]

        # TODO: get the role/attach/policy pattern below using the
        #       `get_tailored_role`

        self.role = aws.iam.Role(
            f"{self.name}-role",
            assume_role_policy=get_service_assume_role("glue.amazonaws.com"),
            opts=ResourceOptions(parent=self),
            tags={"desc_name": (f"{self.desc_name} data crawler role")},
        )

        self.service_role = aws.iam.RolePolicyAttachment(
            f"{self.name}-svcrole",
            role=self.role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole",
            opts=ResourceOptions(parent=self),
        )

        self.role_policy = aws.iam.RolePolicy(
            f"{name}-rlplcy",
            role=self.role.id,
            policy=Output.all(
                buckets=[bucket.bucket for bucket in self.source_buckets],
                db=db.name,
            ).apply(lambda args: get_bucket_reader_policy(args["buckets"])),
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
            f"{self.name}-gcrwl",
            role=self.role.arn,
            database_name=db.name,
            s3_targets=[
                aws.glue.CrawlerS3TargetArgs(
                    path=bucket.bucket.apply(lambda b: f"s3://{b}/")
                )
                for bucket in self.source_buckets
            ],
            classifiers=custom_classifiers,
            opts=ResourceOptions(parent=self),
            tags={"desc_name": self.desc_name or "AWS Glue Data Crawler"},
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"crawler_name": self.crawler.name})

    @property
    def source_buckets(self) -> list[aws.s3.BucketV2]:
        """Property to return the source buckets for triggering the crawler.

        Returns:
            A list of source buckets for triggering the crawler
        """
        return self.buckets


class EtlJob(DescribedComponentResource):
    """An extract/transform/load job."""

    def __init__(
        self,
        name: str,
        raw_bucket: aws.s3.BucketV2,
        clean_bucket: aws.s3.BucketV2,
        script_bucket: aws.s3.BucketV2,
        script_path: str,
        *args,
        default_args: dict | None = None,
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
            script_path: The path in `script_bucket` to the ETL script for this
                        job.
            default_args: default arguments for this ETL job if any.
            opts: The ResourceOptions to apply to the crawler resource.
        Returns:
        """
        # This maintains parental relationships within the pulumi stack
        super().__init__("capeinfra:datalake:Job", name, *args, **kwargs)

        self.name = f"{name}"
        self.raw_bucket = raw_bucket
        self.clean_bucket = clean_bucket

        self.role = aws.iam.Role(
            f"{self.name}-role",
            assume_role_policy=get_service_assume_role("glue.amazonaws.com"),
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} role"},
        )

        self.role_policy = aws.iam.RolePolicy(
            f"{self.name}-roleplcy",
            role=self.role.id,
            policy=Output.all(
                raw_bucket=raw_bucket.bucket,
                clean_bucket=clean_bucket.bucket,
                script_bucket=script_bucket.bucket,
            ).apply(
                lambda args: get_etl_job_s3_policy(
                    args["raw_bucket"],
                    args["clean_bucket"],
                    args["script_bucket"],
                    script_path,
                )
            ),
            opts=ResourceOptions(parent=self),
        )

        self.job = aws.glue.Job(
            self.name,
            role_arn=self.role.arn,
            command=aws.glue.JobCommandArgs(
                script_location=script_bucket.bucket.apply(
                    lambda b: f"s3://{b}/{script_path}"
                ),
                python_version="3",
            ),
            default_arguments=default_args,
            execution_property=aws.glue.JobExecutionPropertyArgs(
                # TODO: this number is just pulled out of thin air to allow
                #       more than one to run at a time. we should figure out
                #       what a good number really is.
                max_concurrent_runs=5,
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
        etl_role = aws.iam.Role(
            f"{self.name}-lmbdtrgrole",
            assume_role_policy=get_service_assume_role("lambda.amazonaws.com"),
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} lambda trigger role"},
        )

        # Attach the Lambda service role for logging privileges
        aws.iam.RolePolicyAttachment(
            f"{self.name}-lmbdsvcroleatch",
            role=etl_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Attach the Lambda service role for logging privileges
        aws.iam.RolePolicy(
            f"{self.name}-lmbdroleplcy",
            role=etl_role.id,
            policy=self.job.name.apply(
                lambda glue_job: get_start_etl_job_policy(glue_job)
            ),
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        etl_function = aws.lambda_.Function(
            f"{self.name}-lmbdtrgfnct",
            role=etl_role.arn,
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/hai_lambda_glue_trigger.py"
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
