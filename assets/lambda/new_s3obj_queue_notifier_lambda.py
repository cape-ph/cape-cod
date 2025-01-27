"""Lambda function for kicking off Epi/HAI Glue Jobs."""

import json
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.dynamodb import EtlTable
from capepy.aws.lambda_ import BucketNotificationRecord
from capepy.aws.meta import Boto3Object
from capepy.aws.utils import decode_error

sqs_client = boto3.client("sqs")


def send_etl_message(
    boto3_object: Boto3Object, queue_name: str, queue_url: str, qmsg: dict
):
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

        boto3_object.logger.exception(
            f"Could not place message with body ({body}) on queue at URL "
            f"({queue_url}). {code} "
            f"{message}"
        )
        raise err

    boto3_object.logger.info(
        f"Message ({body}) SUCCESSFULLY placed on queue at url ({queue_url})"
    )


def index_handler(event, context):
    """Handler for inserting notification events into a specified queue.

    Args:
        event: The event notification object.
        context: Context object.
    """

    queue_name = os.getenv("QUEUE_NAME")

    # obligatory data validation
    if queue_name is None:
        msg = "No queue name provided. Cannot insert notification message."
        return {"statusCode": 500, "body": msg}

    # get a reference to the etl attributes table
    ddb_table = EtlTable()

    try:
        # we'll bucket the incoming object infos and use them to send our
        # response if nothing fails miserably
        ignored_oi = []
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

            while prefix:
                # grab the filtering criteria from dynamodb and see if we care about
                # this object
                etl_attrs = ddb_table.get_etls(bucket_notif.bucket, prefix)

                if etl_attrs:
                    # if the file passes criteria, add message to queue_name
                    if suffix in etl_attrs["suffixes"]:
                        # we care about this object. go ahead and queue a message
                        qmsg = {
                            "bucket": bucket_notif.bucket,
                            "key": bucket_notif.key,
                        }
                        qmsg.setdefault("etl_job", etl_attrs.get("etl_job"))

                        send_etl_message(ddb_table, queue_name, queue_url, qmsg)
                        processed_oi.append(bucket_notif)
                    else:
                        ignored_oi.append(bucket_notif)
                else:
                    ignored_oi.append(bucket_notif)
                prefix, _, _ = prefix.rpartition("/")

        # Make our return message containing info about the processed and
        # ignored objects
        body = ""

        if processed_oi:
            body = (
                "The following objects passed filter criteria and were added to "
                "the ETL queue: ["
            )

            for poi in processed_oi:
                body = f"{body}({poi.bucket}, {poi.key}), "

            body = f"{body}]. "

        if ignored_oi:
            body = (
                f"{body}The following objects were ignored due to not passing "
                f"filter criteria: ["
            )

            for ioi in ignored_oi:
                body = f"{body}({ioi.bucket}, {ioi.key}), "

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

        return {
            "statusCode": 500,
            "body": msg,
        }
