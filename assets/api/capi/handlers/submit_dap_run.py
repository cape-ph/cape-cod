"""Lambda function for handling a post of a new analysis pipeline run."""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

logger = logging.getLogger(__name__)

batch_client = boto3.client("batch")


def _get_batch_configuration():
    """Return Batch resource names supplied by the deployment environment."""

    configuration = {
        "WORKFLOW_QUEUE_NAME": os.getenv("WORKFLOW_QUEUE_NAME"),
        "NEXTFLOW_JOB_DEFINITION_NAME": os.getenv(
            "NEXTFLOW_JOB_DEFINITION_NAME"
        ),
        "JOB_QUEUE_NAME": os.getenv("JOB_QUEUE_NAME"),
    }
    missing = [name for name, value in configuration.items() if not value]
    if missing:
        logger.error(
            "Missing required Batch configuration: %s", ", ".join(missing)
        )
        return None
    return configuration


def index_handler(event, context):
    """Handler for the POST of a new analysis pipeline run.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    batch_configuration = _get_batch_configuration()
    if batch_configuration is None:
        msg = (
            "No AWS Batch queues or job definition configured. "
            "Cannot submit new data analysis pipeline message."
        )
        logger.error(msg)
        return {"statusCode": 500, "body": msg}

    try:
        body = json.loads(event["body"])

        pipeline_project = body["pipelineProject"]
        pipeline_version = body["pipelineVersion"]
        nf_opts = body["nextflowOptions"]

        response = batch_client.submit_job(
            jobName=f"nextflow-{context.aws_request_id}",
            jobQueue=batch_configuration["WORKFLOW_QUEUE_NAME"],
            jobDefinition=batch_configuration["NEXTFLOW_JOB_DEFINITION_NAME"],
            containerOverrides={
                "environment": [
                    {"name": "PIPELINE", "value": pipeline_project},
                    {"name": "PIPELINE_VERSION", "value": pipeline_version},
                    {
                        "name": "PIPELINE_QUEUE",
                        "value": batch_configuration["JOB_QUEUE_NAME"],
                    },
                    {"name": "NF_OPTS", "value": nf_opts},
                ]
            },
        )

        msg = {
            "jobArn": response["jobArn"],
            "jobName": response["jobName"],
            "jobId": response["jobId"],
        }

        # TODO: Add something like DyanmoDB for keeping track and maintaining
        # running pipelines, right now we simply return the job information to
        # the user

        return {
            "statusCode": 200,
            "body": json.dumps(msg),  # return the job information
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
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            },
        }
    except KeyError as ke:
        msg = f"Required value {ke.args[0]} is missing. event: [{event}]"
        print(
            f"Exception caught when processing json payload. {msg}. Error: {ke}"
        )
        return {
            "statusCode": 400,
            "body": msg,
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = (
            f"Error during processing of submitted data analysis pipeline for "
            f"queuing. {code} {message}"
        )
        logger.exception(msg)

        return {
            "statusCode": 500,
            "body": msg,
        }
