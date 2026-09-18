"""Lambda function for handling a post of a new analysis pipeline run."""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.dynamodb import PipelineTable
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


def _get_pipeline_profile(pipeline_name, pipeline_version):
    """Resolve one trusted DAP profile for a submitted pipeline."""

    if not pipeline_name:
        return None

    profiles = PipelineTable().get_pipelines_by_name(
        pipeline_name, pipeline_version
    )
    if not profiles:
        raise ValueError(
            f"No DAP profile found for {pipeline_name}@{pipeline_version}"
        )
    if len(profiles) != 1:
        raise ValueError(
            f"Multiple DAP profiles found for {pipeline_name}@{pipeline_version}"
        )
    return profiles[0]["profile"]


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

        pipeline_version = body["pipelineVersion"]
        nf_opts = body["nextflowOptions"]
        pipeline_profile = _get_pipeline_profile(
            body.get("pipelineName"), pipeline_version
        )
        if pipeline_profile is None:
            pipeline_project = body["pipelineProject"]
            process_overrides = {}
        else:
            pipeline_project = pipeline_profile["project"]
            pipeline_version = pipeline_profile["version"]
            process_overrides = (
                pipeline_profile.get("execution", {})
                .get("nextflow", {})
                .get("processOverrides", {})
            )
            if not isinstance(process_overrides, dict):
                raise ValueError(
                    "DAP Nextflow process overrides must be an object"
                )

        container_environment = [
            {"name": "PIPELINE", "value": pipeline_project},
            {"name": "PIPELINE_VERSION", "value": pipeline_version},
            {
                "name": "PIPELINE_QUEUE",
                "value": batch_configuration["JOB_QUEUE_NAME"],
            },
            {"name": "NF_OPTS", "value": nf_opts},
        ]
        if process_overrides:
            container_environment.append(
                {
                    "name": "NEXTFLOW_PROCESS_OVERRIDES",
                    "value": json.dumps(
                        process_overrides, separators=(",", ":")
                    ),
                }
            )

        response = batch_client.submit_job(
            jobName=f"nextflow-{context.aws_request_id}",
            jobQueue=batch_configuration["WORKFLOW_QUEUE_NAME"],
            jobDefinition=batch_configuration["NEXTFLOW_JOB_DEFINITION_NAME"],
            containerOverrides={"environment": container_environment},
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
    except (KeyError, ValueError) as err:
        msg = f"Required or invalid value is missing: {err.args[0]}"
        print(
            f"Exception caught when processing json payload. {msg}. Error: {err}"
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
