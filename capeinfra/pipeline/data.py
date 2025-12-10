"""Abstractions for data pipelines."""

from copy import deepcopy

import pulumi_aws as aws
from pulumi import ResourceOptions

import capeinfra
from capeinfra.iam import add_resources, aggregate_statements, get_inline_role2
from capeinfra.meta.capemeta import CapeMeta
from capeinfra.resources.objectstorage import VersionedBucket
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
            "classifiers": ["cape-csv-standard-classifier"],
            # a list of exclude paths for the crawler. see here for more:
            # https://docs.aws.amazon.com/glue/latest/dg/define-crawler.html#define-crawler-choose-data-sources
            # NOTE: at this time, all given exclusions apply to all buckets the
            # crawler is set up for.
            "excludes": [],
            # a prefix for the catalog table names
            "prefix": None,
        }

    def __init__(
        self,
        name: str,
        buckets: VersionedBucket | list[VersionedBucket],
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
        self.crawler_role = get_inline_role2(
            self.name,
            f"{self.desc_name} data crawler role",
            "",
            "glue.amazonaws.com",
            aggregate_statements(
                [
                    bucket.bucket.arn.apply(
                        lambda arn: add_resources(
                            bucket.policies[bucket.PolicyEnum.read]
                            + bucket.policies[bucket.PolicyEnum.browse],
                            f"{arn}/*",
                            arn,
                        )
                    )
                    for bucket in self.buckets
                ]
            ),
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

        table_prefix = self.config["prefix"]
        if table_prefix is not None:
            table_prefix = f"{table_prefix}_"
        self.crawler = aws.glue.Crawler(
            f"{self.name}-gcrwl",
            role=self.crawler_role.arn,
            database_name=db.name,
            s3_targets=[
                aws.glue.CrawlerS3TargetArgs(
                    path=bucket.bucket.bucket.apply(
                        lambda b: f"s3://{b}/{prefix+'/' if prefix else ''}"
                    ),
                    exclusions=self.config["excludes"],
                )
                for bucket in buckets
            ],
            classifiers=custom_classifiers,
            schedule=f"cron({self.config['schedule']})",
            table_prefix=table_prefix,
            opts=ResourceOptions(parent=self),
            tags={"desc_name": self.desc_name or "AWS Glue Data Crawler"},
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"crawler_name": self.crawler.name})


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
        src_bucket: VersionedBucket,
        sink_bucket: VersionedBucket,
        script_bucket: VersionedBucket,
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
        self.src_bucket = src_bucket
        self.sink_bucket = sink_bucket

        self.etl_role = get_inline_role2(
            self.name,
            f"{self.desc_name} ETL job role",
            "",
            "glue.amazonaws.com",
            aggregate_statements(
                [capeinfra.meta.policies[CapeMeta.PolicyEnum.logging]]
                + [
                    bucket.bucket.arn.apply(
                        lambda arn: add_resources(
                            bucket.policies[VersionedBucket.PolicyEnum.read],
                            f"{arn}/*",
                            arn,
                        )
                    )
                    for bucket in [
                        src_bucket,
                        capeinfra.meta.automation_assets_bucket,
                    ]
                ]
                + [
                    bucket.bucket.arn.apply(
                        lambda arn: add_resources(
                            bucket.policies[VersionedBucket.PolicyEnum.write],
                            f"{arn}/*",
                            arn,
                        )
                    )
                    for bucket in [sink_bucket]
                ]
                + [
                    bucket.bucket.arn.apply(
                        lambda arn: add_resources(
                            bucket.policies[VersionedBucket.PolicyEnum.read],
                            f"{arn}/{self.config['script']}",
                        )
                    )
                    for bucket in [script_bucket]
                ]
            ),
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

        default_args["--SINK_BUCKET_NAME"] = self.sink_bucket.bucket

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
                script_location=script_bucket.bucket.bucket.apply(
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
