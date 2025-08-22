"""Lambda function for handling a get of an analysis pipeline job status."""

import json
import logging

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

logger = logging.getLogger(__name__)


logs_client = boto3.client("logs")


def bad_param_response():
    """Gets a response data object and status code when bad params are given.

    :return: A tuple containins a response data object and an HTTP 400 status
             code.
    """
    return (
        {
            "message": (
                "Missing required query string parameters: logStreamName"
            )
        },
        400,
    )


def index_handler(event, context):
    """Handler for the GET of available ec2 instances to executing pipelines.

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
            log_stream_name = qsp.get("logStreamName")
            next_token = qsp.get("nextToken")
            limit = qsp.get("limit")
            if log_stream_name is None:
                resp_data, resp_status = bad_param_response()
            else:
                params = {
                    "logStreamName": log_stream_name,
                    "nextToken": next_token,
                    "limit": int(limit) if limit is not None else limit,
                }
                response = logs_client.get_log_events(
                    **{k: v for k, v in params.items() if v is not None}
                )
                keys = [
                    "events",
                    "nextForwardToken",
                    "nextBackwardToken",
                ]
                resp_data = {
                    key: response[key] for key in keys if key in response
                }

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

        msg = f"Error during processing job logs. {code} {message}"
        logger.exception(msg)

        return {
            "statusCode": 500,
            "body": msg,
        }
