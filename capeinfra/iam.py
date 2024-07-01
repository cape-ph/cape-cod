"""Identity and access management constructs.

Helpfully, the big three cloud providers all use this term.
"""

import json
from typing import Callable

import pulumi_aws as aws


def maybe_json(func: Callable) -> Callable:
    """Decorator to return the wrapped function's output as json if specified.

    Args:
        The wrapped function.

    Returns:
        The output of the wrapped function as json if as_json, else the normal
        output.
    """

    def wrapper(*args, **kwargs) -> dict | str:
        d = func(*args, **kwargs)

        return json.dumps(d) if kwargs.get("as_json", False) else d

    return wrapper


@maybe_json
def get_service_assume_role(srvc: str, as_json: bool = True) -> dict | str:
    """Get a role policy statement for assuming a given AWS service.

    Args:
        srvc: The name of the service being assumed (e.g. "glue.amazonaws.com")
        as_json: True if the return should be a string containing the json
                 encoded object. False for a dict (defaults to True)
    Returns:
        The policy statement as a dictionary if as_json is False, or a json
        encoded string of the dict otherwise (which is the default).
    """

    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": srvc},
                "Action": "sts:AssumeRole",
            }
        ],
    }


@maybe_json
def get_bucket_reader_policy(
    buckets: aws.s3.BucketV2 | list[aws.s3.BucketV2], as_json: bool = True
) -> dict | str:
    """Get a role policy statement for Get/List perms on s3 buckets.

    Args:
        buckets: A BucketV2 object or a list of BucketV2 objects to grant
                 Get/List permissions to.
        as_json: True if the return should be a string containing the json
                 encoded object. False for a dict (defaults to True)
    Returns:
        The policy statement as a dictionary if as_json is False, or a json
        encoded string of the dict otherwise (which is the default).
    """

    return {
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
    }


@maybe_json
def get_start_crawler_policy(crawler: str, as_json: bool = True) -> dict | str:
    """Get a role policy statement for starting a crawler.

    Args:
        crawler: The name of the crawler to start
        as_json: True if the return should be a string containing the json
                 encoded object. False for a dict (defaults to True)
    Returns:
        The policy statement as a dictionary if as_json is False, or a json
        encoded string of the dict otherwise (which is the default).
    """

    return {
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
    }


@maybe_json
def get_start_etl_job_policy(job: str, as_json: bool = True) -> dict | str:
    """Get a role policy statement for starting an ETL job.

    Args:
        job: The name of the job being started.
        as_json: True if the return should be a string containing the json
                 encoded object. False for a dict (defaults to True)
    Returns:
        The policy statement as a dictionary if as_json is False, or a json
        encoded string of the dict otherwise (which is the default).
    """

    return {
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
    }


@maybe_json
def get_etl_job_s3_policy(
    raw_bucket: str,
    clean_bucket: str,
    script_bucket: str,
    script_path: str,
    as_json: bool = True,
) -> dict | str:
    """Get a role policy statement for an ETL job to read/write to s3.

    Needed to read from a clean bucket and the bucket containing the ETL script
    as well as to write to the clean bucket.

    Args:
        raw_bucket: The name of the raw bucket.
        clean_bucket: The name of the clean bucket.
        script_bucket: The name of the script bucket.
        script_path: The path to the ETL script in the script bucket.
        as_json: True if the return should be a string containing the json
                 encoded object. False for a dict (defaults to True)
    Returns:
        The policy statement as a dictionary if as_json is False, or a json
        encoded string of the dict otherwise (which is the default).
    """

    return {
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
    }
