"""Lambda for handling GETs listing available rendered reports for a sample.

Report ETLs write pre-rendered HTML reports to the seqauto tributary artifacts
bucket under `reports/<sample_id>/<report_name>.html` (e.g. the RABiTS report at
`reports/<sample_id>/rabits.html`). This handler lists those objects for a given
sample and returns a mapping of report name (the object file name without the
`.html` suffix) to the report HTML, e.g.:

    {"rabits": "<html>...</html>", "bactopia": "<html>...</html>"}

so the front end can render every available report (e.g. as an accordion)
without any further per-report requests. A sample with no reports (or an unknown
sample) returns an empty object.
"""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

logger = logging.getLogger()
logger.setLevel("INFO")

# reports live under this top-level prefix, one "folder" per sample. only
# `.html` objects directly under `reports/<sample_id>/` are returned (nested
# keys and non-html objects are ignored).
REPORTS_PREFIX = "reports"
REPORT_SUFFIX = ".html"

# name of the env var (set by the private swimlane api wiring) holding the name
# of the artifacts bucket that reports are stored in.
REPORTS_BUCKET_ENV_VAR = "REPORTS_BUCKET"


def get_sample_reports(bucket, sample_id):
    """List and load all rendered report HTML for a sample.

    Args:
        bucket: The name of the artifacts bucket the reports are stored in.
        sample_id: The id of the sample whose reports should be loaded.

    Returns:
        A mapping of report name (object file name without the `.html` suffix)
        to the report HTML string. Empty when the sample has no reports.
    """
    s3_client = boto3.client("s3")
    prefix = f"{REPORTS_PREFIX}/{sample_id}/"

    reports = {}
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            # the object name relative to the sample prefix. skip the prefix
            # placeholder, anything nested in a sub-"folder", and non-html
            # objects.
            name = obj["Key"][len(prefix) :]
            if not name.endswith(REPORT_SUFFIX) or "/" in name:
                continue

            report_html = (
                s3_client.get_object(Bucket=bucket, Key=obj["Key"])["Body"]
                .read()
                .decode("utf-8")
            )
            reports[name[: -len(REPORT_SUFFIX)]] = report_html

    return reports


def index_handler(event, context):
    """Handler for the GET listing available reports for a sample.

    :param event: The event object that contains the HTTP request.
    :param context: Context object.
    """

    try:
        # assume the best will happen and set our output up for success
        resp_status = 200
        resp_data = {}
        resp_headers = {
            "Content-Type": "application/json",
            # TODO: ISSUE #141 CORS bypass. We do not want this long term.
            #       When we get all the api and web resources on the same
            #       domain, this may not matter too much. But we may
            #       eventually end up with needing to handle requests from
            #       one domain served up by another domain in a lambda
            #       handler. In that case we'd need to be able to handle
            #       CORS, and would want to look into allowing
            #       configuration of the lambda (via pulumi config that
            #       turns into env vars for the lambda) that set the
            #       origins allowed for CORS.
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,GET",
        }

        qsp = event.get("queryStringParameters")
        sample_id = qsp.get("sampleId") if qsp else None

        if sample_id is None:
            resp_status = 400
            resp_data = {
                "message": "Missing required query string parameters: sampleId"
            }
        else:
            reports = get_sample_reports(
                os.environ[REPORTS_BUCKET_ENV_VAR], sample_id
            )
            resp_data = reports

        return {
            "statusCode": resp_status,
            "headers": resp_headers,
            "body": json.dumps(resp_data),
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = f"Error during fetch of sample reports. {code} {message}"

        return {
            "statusCode": 500,
            "body": msg,
        }
    except Exception as e:
        msg = f"{e}"
        return {
            "statusCode": 500,
            "body": msg,
        }
