"""Lambda function for handling a post of a new analysis pipeline run."""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

sqs_client = boto3.client("sqs")


# TODO: this function appears with the same name in the
#       new_s3obj_queue_notifier_lambda.py module as well. And we will likely
#       have a similar function in any lambda that is tasked with handling a
#       ClientError. We should move this to a common place (which is a
#       little complicated as we would need to ensure the common module is
#       deployed to different lambda environments)
def decode_error(err: ClientError):
    """Decode a ClientError from AWS.

    Args:
        err: The ClientError being decoded.

    Returns:
        A tuple containg the error code and the error message provided by AWS.
    """
    code, message = "Unknown", "Unknown"
    if "Error" in err.response:
        error = err.response["Error"]
        if "Code" in error:
            code = error["Code"]
        if "Message" in error:
            message = error["Message"]
    return code, message


# TODO: this function appears with a different name in the
#       new_s3obj_queue_notifier_lambda.py module as well. And we will likely
#       have a similar function in any lambda that is tasked with sending a
#       message to a queue. We should move this to a common place (which is a
#       little complicated as we would need to ensure the common module is
#       deployed to different lambda environments)
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

    # TODO this should be removed before any real deployment (dev is ok)
    print(
        f"Analysis Pipeline API (POST new pipeline run) received event: "
        f"{json.dumps(event, indent=2)} with context {context}"
    )

    queue_name = os.getenv("DAP_QUEUE_NAME")

    # obligatory data validation
    if queue_name is None:
        msg = "No queue name provided. Cannot submit new data analysis pipeline message."
        logger.error(msg)
        return {"statusCode": 500, "body": msg}

    try:
        body = json.loads(event["body"])

        # TODO: we need to figure out the actual set of params we'll need from
        #       this endpoint. this will depend on what's needed to run the
        #       actual pipeline.
        pipeline_name = body["pipelineName"]
        pipeline_version = body["pipelineVersion"]
        # TODO: these paths (if we keep using them) may be url encoded when we
        #       actually get to more real stuff. not sure and could depend how 
        #       we wire it up to UI. since this is a passthrough to a queue to
        #       be processed later, we may want to do the decode (if needed)
        #       there...
        input_path = body["inputPath"]
        output_path = body["outputPath"]

        msg = (
            f"Data analsysis pipeline {pipeline_name} (version "
            f"{pipeline_version} will be scheduled using input path "
            f"[{input_path}] and output path [{output_path}]"
        )

        logger.info(msg)

        response = sqs_client.get_queue_url(QueueName=queue_name)
        queue_url = response["QueueUrl"]

        # NOTE: we just blindly put the message in the queue. all fitlering of
        #       invalid values (e.g. a pipeline name that doesn't exist) will
        #       happen in the processing of the message from the queue in a
        #       different lambda.
        qmsg = {
            "pipeline_name": pipeline_name,
            "pipeline_version": pipeline_version,
            "input_path": input_path,
            "output_path": output_path,
        }

        send_submit_dap_message(queue_name, queue_url, qmsg)

        return {
            "statusCode": 200,
            "body": msg,
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
