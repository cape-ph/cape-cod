"""Lambda function for kicking off Epi/HAI Glue Jobs."""

import json
import logging
import os
import urllib.parse

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

sqs_client = boto3.client("sqs")

# TODO: need to be able to parameterize the region for our whole cape setup...
ddb_resource = boto3.resource("dynamodb", region_name="us-east-2")


def get_etl_attrs_table(table_name: str) -> boto3.resource:
    """Get a DynamoDB table by name.

    Args:
        table_name: The name of the table to get a reference to.

    Returns:
        A reference to the table.

    Raises:
        ClientError: If the table cannot be found or other client error.
    """
    try:
        table = ddb_resource.Table(table_name)
        table.load()
    except ClientError as err:
        if err.response["Error"]["Code"] == "ResourceNotFoundException":
            msg = (
                f"CAPE ETL attributes DynamoDB table ({table_name}) could not"
                f"be found: {err.response['Error']['Code']} "
                f"{err.response['Error']['Message']}",
            )
        else:
            msg = (
                f"Error trying to access CAPE ETL attributes DynamoDB table "
                f"({table_name}): {err.response['Error']['Code']} "
                f"{err.response['Error']['Message']}",
            )

        logger.error(msg)
        raise err

    return table


def get_etl_attrs(
    table: boto3.resource, bucket_name: str, prefix: str
) -> dict | None:
    """Get the ETL attributes from the DynamoDB table.

    Args:
        table: A reference to the DyanmoDB table.
        bucket_name: The name of the bucket the attrs apply to.
        prefix: The prefix in the S3 bucket attrs apply to.

    Returns:
        A dict containing the ETL attrs for the S3 bucket and prefix.

    Raises:
        ClientError: If no table items can be found for the S3 bucket name and
                     prefix.
    """
    ret = None
    try:
        response = table.get_item(
            Key={"bucket_name": bucket_name, "prefix": prefix}
        )

        ret = response["Item"]

    except ClientError as err:
        # in this case we really just need to ignore the object, but we'll log
        # for the time being
        logger.error(
            f"Couldn't get ETL attributes for bucket '{bucket_name}' and "
            f"prefix '{prefix}'. {err.response['Error']['Code']} "
            f"{err.response['Error']['Message']}"
        )

    return ret


def send_etl_message(queue_url: str, obj_info: dict):
    """Send the object info as a json message to the specified queue.

    Args:
        queue_url: The URL of the queue to send the message to.
        obj_info: A dict containing info about the new S3 object that needs to
                  be processed by ETL.

    Raises:
        ClientError: On any error in sending the message.
    """
    body = json.dumps(obj_info)
    try:
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=body,
        )
    except ClientError as err:
        logger.exception(
            f"Could not place message with body ({body}) on queue at URL "
            f"({queue_url}). {err.response['Error']['Code']} "
            f"{err.response['Error']['Message']}"
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
    etl_attrs_ddb_name = os.getenv("TRIB_ATTRS_DDB")

    # obligatory data validation
    if queue_name is None:
        msg = "No queue name provided. Cannot insert notification message."
        logger.error(msg)
        return {"statusCode": 500, "body": msg}

    if etl_attrs_ddb_name is None:
        msg = (
            "No ETL attributes DynamoDB table name provided. Cannot insert "
            "notification message."
        )
        logger.error(msg)
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

    # get a reference to the tribuitary attributes table
    ddb_table = get_etl_attrs_table(etl_attrs_ddb_name)

    try:
        # we'll bucket the incoming object infos and use them to send our
        # response if nothing fails miserably
        ignored_oi = []
        processed_oi = []

        queue_url = sqs_client.get_queue_by_name(QueueName=queue_name)

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

            # grab the filtering criteria from dynamodb and see if we care about
            # this object
            etl_attrs = get_etl_attrs(ddb_table, oi["bucket"], prefix)

            if etl_attrs:
                # if the file passes criteria, add message to queue_name
                if suffix in etl_attrs["suffixes"]:
                    # we care about this object. go ahead and queue a message
                    send_etl_message(queue_url, oi)
                    processed_oi.append(oi)
                else:
                    ignored_oi.append(oi)
            else:
                ignored_oi.append(oi)

        # Make our return message containing info about the processed and
        # ignored objects
        body = ""

        if processed_oi:
            body = (
                "The following objects passed filter criteria and were added to "
                "the ETL queue: ["
            )

            for poi in processed_oi:
                body = f"{body}({poi['bucket']}, {poi['key']}), "

            body = f"{body}]. "

        if ignored_oi:
            body = (
                f"{body}The following objects were ignored due to not passing "
                f"filter criteria: ["
            )

            for ioi in ignored_oi:
                body = f"{body}({ioi['bucket']}, {ioi['key']}), "

            body = f"{body}]. "

        return {
            "statusCode": 200,
            "body": body,
        }
    except ClientError as err:
        msg = (
            f"Error during processing of new object notification for queuing. "
            f"{err.response['Error']['Code']} "
            f"{err.response['Error']['Message']}"
        )
        logger.exception(msg)

        return {
            "statusCode": 500,
            "body": msg,
        }