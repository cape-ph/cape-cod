"""Lambda function for handling a post of a new analysis pipeline run."""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.dynamodb import PipelineTable
from capepy.aws.utils import (
    decode_error,
    json_serialize_the_unserializable,
)

logger = logging.getLogger(__name__)

batch_client = boto3.client("batch")


def _parse_execution_class_queue_map(raw_value):
    """Parse the trusted execution-class to Batch-queue mapping."""

    if not raw_value:
        return {}
    try:
        routes = json.loads(raw_value)
    except json.JSONDecodeError:
        logger.error("Invalid execution-class queue map JSON")
        return None
    if not isinstance(routes, dict) or any(
        not isinstance(execution_class, str)
        or not execution_class
        or not isinstance(queue_name, str)
        or not queue_name
        for execution_class, queue_name in routes.items()
    ):
        logger.error("Invalid execution-class queue map structure")
        return None
    return routes


def _get_batch_configuration():
    """Return Batch resource names supplied by the deployment environment."""

    configuration = {
        "WORKFLOW_QUEUE_NAME": os.getenv("WORKFLOW_QUEUE_NAME"),
        "NEXTFLOW_JOB_DEFINITION_NAME": os.getenv(
            "NEXTFLOW_JOB_DEFINITION_NAME"
        ),
        "JOB_QUEUE_NAME": os.getenv("JOB_QUEUE_NAME"),
        "EXECUTION_CLASS_QUEUE_MAP": _parse_execution_class_queue_map(
            os.getenv("EXECUTION_CLASS_QUEUE_MAP")
        ),
    }
    missing = [
        name
        for name in (
            "WORKFLOW_QUEUE_NAME",
            "NEXTFLOW_JOB_DEFINITION_NAME",
            "JOB_QUEUE_NAME",
        )
        if not configuration[name]
    ]
    if missing or configuration["EXECUTION_CLASS_QUEUE_MAP"] is None:
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


def _get_pipeline_queue(pipeline_profile, batch_configuration):
    """Resolve the trusted profile's child queue, with a legacy fallback."""

    if pipeline_profile is None:
        return batch_configuration["JOB_QUEUE_NAME"]

    execution = pipeline_profile.get("execution", {})
    if execution is None:
        execution = {}
    if not isinstance(execution, dict):
        raise ValueError("DAP execution configuration must be an object")

    execution_class = execution.get("class")
    if execution_class is None:
        return batch_configuration["JOB_QUEUE_NAME"]
    if not isinstance(execution_class, str) or not execution_class:
        raise ValueError("DAP execution class must be a non-empty string")

    queue_name = batch_configuration["EXECUTION_CLASS_QUEUE_MAP"].get(
        execution_class
    )
    if not queue_name:
        raise ValueError(
            f"No Batch queue configured for execution class {execution_class}"
        )
    return queue_name


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
            execution = pipeline_profile.get("execution", {})
            if execution is None:
                execution = {}
            if not isinstance(execution, dict):
                raise ValueError(
                    "DAP execution configuration must be an object"
                )
            process_overrides = execution.get("nextflow", {}).get(
                "processOverrides", {}
            )
            if not isinstance(process_overrides, dict):
                raise ValueError(
                    "DAP Nextflow process overrides must be an object"
                )

        pipeline_queue = _get_pipeline_queue(
            pipeline_profile, batch_configuration
        )
        container_environment = [
            {"name": "PIPELINE", "value": pipeline_project},
            {"name": "PIPELINE_VERSION", "value": pipeline_version},
            {"name": "PIPELINE_QUEUE", "value": pipeline_queue},
            {"name": "NF_OPTS", "value": nf_opts},
        ]
        if process_overrides:
            container_environment.append(
                {
                    "name": "NEXTFLOW_PROCESS_OVERRIDES",
                    "value": json.dumps(
                        process_overrides,
                        default=json_serialize_the_unserializable,
                        separators=(",", ":"),
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
