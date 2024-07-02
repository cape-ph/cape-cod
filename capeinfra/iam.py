"""Identity and access management constructs.

Helpfully, the big three cloud providers all use this term.
"""

import json

import pulumi_aws as aws


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
