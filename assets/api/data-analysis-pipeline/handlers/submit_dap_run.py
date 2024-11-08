"""Lambda function for handling a post of a new analysis pipeline run."""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

logger = logging.getLogger(__name__)

sqs_client = boto3.client("sqs")


# TODO: ISSUE #86
def send_submit_dap_message(queue_name: str, queue_url: str, qmsg: dict):
    """Send the new DAP sumission as a json message to the specified queue.

    Args:
        queue_name: The name of the queue to send the message to. This is needed
                    to make a message group id for the fifo queue.
        queue_url: The URL of the queue to send the message to.
        qmsg: A dict containing info about the new DAP being submitted to be
              run.

    Raises:
        ClientError: On any error in sending the message.
    """
    body = json.dumps(qmsg)
    try:
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=body,
            MessageGroupId=f"{queue_name}-raw-data-msg",
        )
    except ClientError as err:
        code, message = decode_error(err)

        logger.exception(
            f"Could not place message with body ({body}) on queue at URL "
            f"({queue_url}). {code} "
            f"{message}"
        )
        raise err

    logger.info(
        f"Message ({body}) SUCCESSFULLY placed on queue at url ({queue_url})"
    )


def index_handler(event, context):
    """Handler for the POST of a new analysis pipeline run.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    queue_name = os.getenv("DAP_QUEUE_NAME")

    # obligatory data validation
    if queue_name is None:
        msg = "No queue name provided. Cannot submit new data analysis pipeline message."
        logger.error(msg)
        return {"statusCode": 500, "body": msg}

    try:
        body = json.loads(event["body"])

        pipeline_name = body["pipelineName"]
        pipeline_version = body["pipelineVersion"]
        output_path = body["outputPath"]
        # TODO: ISSUE #TBD all below fields are specific to bactopia right
        #       now...
        r1_path = body["r1Path"]
        r2_path = body["r2Path"]
        ec2_id = body["ec2Id"]
        sample = body["sample"]

        msg = (
            f"Data analysis pipeline {pipeline_name} (version "
            f"{pipeline_version}) will be sent to the sumission queue with "
            f"r1 path [{r1_path}], r2 path [{r2_path}], sample [{sample}], "
            f"output path [{output_path}], and EC2 instance [{ec2_id}]."
        )

        print(msg)

        response = sqs_client.get_queue_url(QueueName=queue_name)
        queue_url = response["QueueUrl"]

        # NOTE: we just blindly put the message in the queue. all filtering of
        #       invalid values (e.g. a pipeline name that doesn't exist) will
        #       happen in the processing of the message from the queue in a
        #       different lambda.
        # TODO: Feels we should add a DAPipelineSpec class or something to
        #       capepy lib that can be reused across lambdas instead of a hard
        #       coded dict here. would understand outermost keys, and be able
        #       to be constructed with a collection of pipeline param keys
        #       (maybe with some validation meta as well). deferring that for a
        #       bit tho. could also just mod the PipelineRecord class for the
        #       same purpose and have it be able to serialize/deserialize
        #       to/from dicts for jsoning.
        qmsg = {
            "pipeline_name": pipeline_name,
            "pipeline_version": pipeline_version,
            "pipeline_parameters": {
                "output_path": output_path,
                "r1_path": r1_path,
                "r2_path": r2_path,
                "sample": sample,
                "ec2_id": ec2_id,
            },
        }

        send_submit_dap_message(queue_name, queue_url, qmsg)

        return {
            "statusCode": 200,
            "body": msg,
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
