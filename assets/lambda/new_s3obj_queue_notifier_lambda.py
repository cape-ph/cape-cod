"""Lambda function for kicking off Epi/HAI Glue Jobs."""

import json
import os
import urllib.parse

import boto3

sqs_client = boto3.client("sqs")


def index_handler(event, context):
    """Handler for inserting notification events into a specified queue.

    :param event: The event notification object.
    :param context: Context object.
    """

    queue_name = os.getenv("QUEUE_NAME")

    if queue_name is None:
        msg = "No queue name provided. Cannot insert notification message."
        print(msg)
        return {"statusCode": 500, "body": msg}

    # grab all the info we care about for the new s3 object from the event
    # object.
    # NOTE: the event structure for notifications can contain many records.
    #       grabbing them all to handle potential of multiple uploads in a
    #       batch. a new message will be inserted for each record
    object_info = [
        {
            "bucket": rec["s3"]["bucket"]["name"],
            "key": urllib.parse.unquote_plus(
                rec["s3"]["object"]["key"], encoding="utf-8"
            ),
        }
        for rec in event["Records"]
    ]

    try:
        for oi in object_info:
            # deconstruct the key (s3 name, prefix, suffix)

            prefix, _, objname = oi["key"].rpartition("/")
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

            # LEFTOFF

            # - grab the filtering criteria from dynamodb
            # - if the file passes criteria, add message to queue_name
            # - else log message about skipping file and exit
            return {
                "statusCode": 200,
                "body": (
                    f"New s3 ({oi['bucket']}) object ({oi['key']}) passed "
                    f"filtering and message added to queue {queue_name} for "
                    f"later processing"
                ),
            }
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": f"TODO: FIGURE OUT WHAT CAN BREAK HERE: {str(e)}",
        }
