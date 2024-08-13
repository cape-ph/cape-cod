"""Identity and access management constructs.

Helpfully, the big three cloud providers all use this term.
"""

import json

import pulumi_aws as aws
from pulumi import Output, ResourceOptions


def get_service_assume_role(srvc: str) -> str:
    """Get a role policy statement for assuming a given AWS service.

    Args:
        srvc: The name of the service being assumed (e.g. "glue.amazonaws.com")

    Returns:
        The policy statement as a json encoded string.
    """

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": srvc},
                    "Action": "sts:AssumeRole",
                }
            ],
        },
    )


def get_bucket_reader_policy(
    buckets: aws.s3.BucketV2 | list[aws.s3.BucketV2],
) -> str:
    """Get a role policy statement for Get/List perms on s3 buckets.

    Args:
        buckets: A BucketV2 object or a list of BucketV2 objects to grant
                 Get/List permissions to.

    Returns:
        The policy statement as a json encoded string.
    """
    buckets = [buckets] if isinstance(buckets, aws.s3.BucketV2) else buckets
    return json.dumps(
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
                for bucket in buckets
            ],
        },
    )


def get_start_crawler_policy(crawler: str) -> str:
    """Get a role policy statement for starting a crawler.

    Args:
        crawler: The name of the crawler to start

    Returns:
        The policy statement as a json encoded string.
    """

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "glue:StartCrawler",
                        "glue:GetCrawler",
                    ],
                    "Resource": [f"arn:aws:glue:*:*:crawler/{crawler}"],
                },
            ],
        },
    )


def get_start_etl_job_policy(job: str) -> str:
    """Get a role policy statement for starting an ETL job.

    Args:
        job: The name of the job being started.

    Returns:
        The policy statement as a json encoded string.
    """

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "glue:StartJobRun",
                        "glue:GetJobRun",
                    ],
                    "Resource": [f"arn:aws:glue:*:*:job/{job}"],
                },
            ],
        },
    )


def get_etl_job_s3_policy(
    raw_bucket: str,
    clean_bucket: str,
    script_bucket: str,
    script_path: str,
) -> str:
    """Get a role policy statement for an ETL job to read/write to s3.

    Needed to read from a clean bucket and the bucket containing the ETL script
    as well as to write to the clean bucket.

    Args:
        raw_bucket: The name of the raw bucket.
        clean_bucket: The name of the clean bucket.
        script_bucket: The name of the script bucket.
        script_path: The path to the ETL script in the script bucket.

    Returns:
        The policy statement as a dictionary json encoded string.
    """

    return json.dumps(
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
                        f"arn:aws:s3:::{script_bucket}/{script_path}",
                        f"arn:aws:s3:::{raw_bucket}/*",
                        f"arn:aws:s3:::{raw_bucket}",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:PutObject"],
                    "Resource": [
                        f"arn:aws:s3:::{clean_bucket}/*",
                        f"arn:aws:s3:::{clean_bucket}",
                    ],
                },
            ],
        },
    )


def get_sqs_raw_notifier_policy(
    queue_name: str, etl_attr_ddb_table_name: str
) -> str:
    """Get a role policy statement for reading dynamodb and writing sqs.

    This policy allows for actions on an sqs queue, a dynamodb table and
    logging necessary for raw data handlers to place metadata about a new S3
    object into a specific SQS queue and to read some of the metadata from a
    dynamodb table.

    Args:
        queue_name: the name of the queue to grant access to.
        etl_attr_ddb_table_name: The name of the DynamoDB table storing the ETL
                                 attributes.

    Returns:
        The policy statement as a dictionary json encoded string.
    """

    return json.dumps(
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
                    "Action": [
                        "sqs:GetQueueUrl",
                        "sqs:SendMessage",
                    ],
                    "Resource": [
                        f"arn:aws:sqs:*:*:{queue_name}",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:DescribeTable",
                        "dynamodb:GetItem",
                    ],
                    "Resource": [
                        f"arn:aws:dynamodb:*:*:table/{etl_attr_ddb_table_name}",
                    ],
                },
            ],
        },
    )


def get_sqs_lambda_glue_trigger_policy(queue_name: str, job_names: list) -> str:
    """Get a role policy statement for reading from sqs and starting glue jobs.

    This policy allows for actions on an sqs queue, configured glue jobs and
    logging necessary for SQS trigger functions to read metadata from an SQS
    queue and to start ETL glue jobs with the metadata.

    Args:
        queue_name: the name of the queue to grant access to.
        job_names: a list of ETL job names that this policy will allow execution
                   of.

    Returns:
        The policy statement as a dictionary json encoded string.
    """

    return json.dumps(
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
                    "Action": [
                        # This is the bare minimum required for an SQS notified
                        # lambda to do its job.
                        "sqs:GetQueueAttributes",
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                    ],
                    "Resource": [
                        f"arn:aws:sqs:*:*:{queue_name}",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "glue:StartJobRun",
                        "glue:GetJobRun",
                    ],
                    "Resource": [
                        f"arn:aws:glue:*:*:job/{job}" for job in job_names
                    ],
                },
            ],
        },
    )


# TODO: feels like we could do roles/poilicies better. most of ours are inline
#       (as opposed to managed), and many are the same minus a specific bucket
#       name or something like that. need to figure out how to improve.
# NOTE: done as a function for now because this pattern is in a number of
#       places (lambda trigger functions, data crawlers, glue jobs, etc)
def get_inline_role(
    name: str,
    desc_name: str,
    srvc_prfx: str,
    assume_role_srvc: str,
    role_policy: Output | None = None,
    srvc_policy_attach: str | None = None,
    opts: ResourceOptions | None = None,
) -> aws.iam.Role:
    """Get an inline role fir the given arguments.

    Args:
        name: The resource name the role is being used on.
        desc_name: The descriptive name (e.g. for tagging) for the role. this
                   will be used as-is, so it needs to be fully rendered
        srvc_prfx: the service prefix to use in the name (e.g. `lmbd` for aws
                   lambda)
        role_policy: The policy to attach to the role.
        srvc_policy_attach: Optional identified (e.g. ARN for aws) for a service
                            role policy to attach to the role in addition to the
                            role_policy
        opts: The pulumi ResourceOptions to add to ComponentResources created
              here.

    Returns:
        The inline role.
    """
    # first create the inline role
    inline_role = aws.iam.Role(
        f"{name}-{srvc_prfx}role",
        assume_role_policy=get_service_assume_role(assume_role_srvc),
        opts=opts,
        tags={"desc_name": desc_name},
    )

    # if we were told to also attach a service role's policy, do so
    if srvc_policy_attach is not None:
        aws.iam.RolePolicyAttachment(
            f"{name}-{srvc_prfx}svcroleatch",
            role=inline_role.name,
            policy_arn=srvc_policy_attach,
            opts=opts,
        )

    # and now add the policy rules we were given to the role if configured
    if role_policy is not None:
        aws.iam.RolePolicy(
            f"{name}-{srvc_prfx}roleplcy",
            role=inline_role.id,
            policy=role_policy,
            opts=opts,
        )

    return inline_role
