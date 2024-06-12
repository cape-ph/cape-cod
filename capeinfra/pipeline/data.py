"""Abstractions for data pipelines."""

import json

import pulumi_aws as aws
from pulumi import AssetArchive, ComponentResource, FileAsset, Output, ResourceOptions

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


class DataCrawler(ComponentResource):
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


class EtlJob(ComponentResource):
    def __init__(
        self,
        name: str,
        raw_bucket: aws.s3.BucketV2,
        clean_bucket: aws.s3.BucketV2,
        script_bucket: aws.s3.BucketV2,
        script_path: str,
        default_args: dict | None = None,
        opts=None,
    ):
        # By calling super(), we ensure any instantiation of this class
        # inherits from the ComponentResource class so we don't have to declare
        # all the same things all over again.
        super().__init__("capeinfra:datalake:Job", name, None, opts)

        self.name = f"{name}-etl-job"
        self.raw_bucket = raw_bucket
        self.clean_bucket = clean_bucket

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

        self.role_policy = aws.iam.RolePolicy(
            f"{self.name}-role-policy",
            role=self.role.id,
            policy=Output.all(
                raw_bucket=raw_bucket.bucket,
                clean_bucket=clean_bucket.bucket,
                script_bucket=script_bucket.bucket,
            ).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "logs:PutLogEvents",
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                ],
                                "Resource": "arn:aws:logs:*:*:*",
                            },
                            {
                                "Effect": "Allow",
                                "Action": ["s3:GetObject"],
                                "Resource": [
                                    f"arn:aws:s3:::{args['script_bucket']}/{script_path}",
                                    f"arn:aws:s3:::{args['raw_bucket']}/*",
                                    f"arn:aws:s3:::{args['raw_bucket']}",
                                ],
                            },
                            {
                                "Effect": "Allow",
                                "Action": ["s3:PutObject"],
                                "Resource": [
                                    f"arn:aws:s3:::{args['clean_bucket']}/*",
                                    f"arn:aws:s3:::{args['clean_bucket']}",
                                ],
                            },
                        ],
                    }
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
                # TODO: this number is just pulled out of thin air to allow more
                #       than one to run at a time. we should figure out what a good
                #       number really is.
                max_concurrent_runs=5,
            ),
            opts=ResourceOptions(parent=self),
        )
        self.register_outputs({"job_name": self.job.name})

    def add_trigger_function(self):
        """"""
        etl_role = aws.iam.Role(
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
            role=etl_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Attach the Lambda service role for logging privileges
        aws.iam.RolePolicy(
            f"{self.name}-lambda-role-policy",
            role=etl_role.id,
            policy=self.job.name.apply(
                lambda glue_job: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["glue:StartJobRun", "glue:GetJobRun"],
                                "Resource": [f"arn:aws:glue:*:*:job/{glue_job}"],
                            },
                        ],
                    }
                )
            ),
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        etl_function = aws.lambda_.Function(
            f"{self.name}-lambda-trigger-function",
            role=etl_role.arn,
            code=AssetArchive(
                {"index.py": FileAsset("./assets/lambda/hai_lambda_glue_trigger.py")}
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
        )

        # Give our function permission to invoke
        etl_permission = aws.lambda_.Permission(
            f"{self.name}-allow-raw-bucket-etl-lambda",
            action="lambda:InvokeFunction",
            function=etl_function.arn,
            principal="s3.amazonaws.com",
            source_arn=self.raw_bucket.arn,
            opts=ResourceOptions(parent=self),
        )

        return etl_function, etl_permission
