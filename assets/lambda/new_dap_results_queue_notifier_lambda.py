"""Lambda function for sending an SQS message about new DAP results in s3."""

# TODO: ISSUE #150 We should look at how to minimize DRY between this and the
#       `new_s3obj_queue_notifier.py` lambda.
#       This is very similar to the lambda used for doing this same kind of
#       thing on new raw data in HAI/EPI. A big difference is that there is
#       a DynamoDB table used in the raw data case that maps a lot of the s3
#       object data to a specific ETL function. In this case, we don't have that
#       (yet at least) and any implementation like that would need to wait until
#       we really know how we're going to handle pipeline data.

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.lambda_ import BucketNotificationRecord
from capepy.aws.utils import decode_error

logger = logging.getLogger(__name__)

sqs_client = boto3.client("sqs")


# TODO: ISSUE #86
def send_etl_message(queue_name: str, queue_url: str, qmsg: dict):
    """Send the object info as a json message to the specified queue.

    Args:
        queue_name: The name of the queue to send the message to. This is needed
                    to make a message group id for the fifo queue.
        queue_url: The URL of the queue to send the message to.
        qmsg: A dict containing info about the new S3 object and ETL job that
              needs to be processed by ETL.

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
    """Handler for inserting notification events into a specified queue.

    Args:
        event: The event notification object.
        context: Context object.
    """

    queue_name = os.getenv("QUEUE_NAME")
    etl_job_id = os.getenv("ETL_JOB_ID")

    # obligatory data validation
    if queue_name is None:
        msg = "No queue name provided. Cannot insert notification message."
        logger.error(msg)
        return {"statusCode": 500, "body": msg}

    try:
        # we'll bucket the incoming object infos and use them to send our
        # response if nothing fails miserably
        processed_oi = []

        # TODO: any other error checking here? we should get an exception if
        #       the response isn't valid...
        response = sqs_client.get_queue_url(QueueName=queue_name)
        queue_url = response["QueueUrl"]

        for rec in event["Records"]:
            bucket_notif = BucketNotificationRecord(rec)
            # deconstruct the key (s3 name, prefix, suffix)
            prefix, _, objname = bucket_notif.key.rpartition("/")
            if not objname:
                # if we didn't get an objname, the separator "/" was not found,
                # meaning there is no prefix. so do some rearranging of
                # variables
                objname = prefix
                prefix = ""

            # NOTE: if the object deosn't have a file extension, suffix will end
            #       up an empty string here. that's ok if the ETL is configured
            #       to work for items with no extension
            _, _, suffix = objname.rpartition(".")

            # NOTE: first cut DAP results processing, we'll assume all files
            #       coming in will be ETL'd
            qmsg = {
                "bucket": bucket_notif.bucket,
                "key": bucket_notif.key,
            }
            qmsg.setdefault("etl_job", etl_job_id)

            send_etl_message(queue_name, queue_url, qmsg)
            processed_oi.append(bucket_notif)

        # Make our return message containing info about the processed objects
        body = ""

        if processed_oi:
            body = (
                "The following objects passed filter criteria and were added to "
                "the ETL queue: ["
            )

            for poi in processed_oi:
                body = f"{body}({poi.bucket}, {poi.key}), "

            body = f"{body}]. "

        return {
            "statusCode": 200,
            "body": body,
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = (
            f"Error during processing of new object notification for queuing. "
            f"{code} "
            f"{message}"
        )
        logger.exception(msg)

        return {
            "statusCode": 500,
            "body": msg,
        }
