"""Lambda function for handling a get of an analysis pipeline job status."""

import json
import logging

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

logger = logging.getLogger(__name__)


batch_client = boto3.client("batch")


def bad_param_response():
    """Gets a response data object and status code when bad params are given.

    :return: A tuple containins a response data object and an HTTP 400 status
             code.
    """
    return (
        {"message": ("Missing required query string parameters: jobId")},
        400,
    )


def extract_object_keys(obj, keys):
    out = {}
    for key in keys:
        if key in obj:
            out[key] = obj[key]
    return out


def index_handler(event, context):
    """Handler for the GET of status of analysis pipeline jobs.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    try:
        qsp = event.get("queryStringParameters")

        resp_status = 200
        if qsp is None:
            resp_data, resp_status = bad_param_response()
        else:
            job_id = qsp.get("jobId")
            if job_id is None:
                resp_data, resp_status = bad_param_response()
            else:
                response = batch_client.describe_jobs(jobs=[job_id])
                job = response["jobs"][0]
                resp_data = extract_object_keys(
                    job,
                    [
                        "jobName",
                        "jobArn",
                        "jobId",
                        "status",
                        "statusReason",
                        "isCancelled",
                        "isTerminated",
                        "createdAt",
                        "startedAt",
                        "stoppedAt",
                    ],
                )
                resp_data["environment"] = {}
                if "container" in job:
                    container_data = job["container"]
                    if "logStreamName" in container_data:
                        resp_data["logStreamName"] = container_data[
                            "logStreamName"
                        ]
                    for env_var in container_data.get("environment", []):
                        resp_data["environment"][env_var["name"]] = env_var[
                            "value"
                        ]

        return {
            "statusCode": resp_status,
            "headers": {
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
            },
            "body": json.dumps(resp_data),
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = (
            f"Error during processing of checking job status. {code} {message}"
        )
        logger.exception(msg)

        return {
            "statusCode": 500,
            "body": msg,
        }
