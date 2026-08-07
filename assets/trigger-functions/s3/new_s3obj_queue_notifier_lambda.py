"""Lambda function for kicking off Epi/HAI Glue Jobs."""

import hashlib
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


def derive_message_group_id(key: str, prefix: str) -> str:
    """Build a FIFO MessageGroupId that stays within the SQS 128-char limit.

    SQS rejects any MessageGroupId longer than 128 characters, so the raw
    object key cannot be used directly: long split-read keys overflow the
    limit and the send fails. We preserve the per-object-key semantics
    (distinct keys map to distinct groups, so notifications deliver in
    parallel across keys and stay ordered per key) by hashing the full key,
    and prepend a short readable prefix for debuggability.

    Args:
        key: The full S3 object key the message is about.
        prefix: A readable label (e.g. tributary or rule name), truncated to
                63 chars so the total stays within the 128-char limit.

    Returns:
        A group id of the form "<prefix[:63]>-<sha256 hex>", always <= 128
        characters (63 + 1 + 64).
    """
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"{prefix[:63]}-{digest}"


def send_notify_message(
    boto3_object: Boto3Object,
    queue_url: str | None,
    message_group_id: str,
    qmsg: dict,
):
    """Send a data notification message as json to the notify queue.

    Args:
        queue_url: The URL of the notify queue to send the message to.
        message_group_id: The FIFO message group id to use. Callers pass a
                           bounded id (see derive_message_group_id) that stays
                           within the SQS 128-char limit while preserving
                           per-key grouping, so distinct objects deliver in
                           parallel and redeliveries of the same object stay in
                           one group.
        qmsg: A dict containing the data notification message body.

    Raises:
        ClientError: On any error in sending the message.
    """
    body = json.dumps(qmsg)
    try:
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=body,
            MessageGroupId=message_group_id,
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


def match_notify_rules(bucket: str, key: str, rules: dict) -> list[str]:
    """Return the names of the data notification rules that match an object.

    Args:
        bucket: The physical bucket name the object lives in.
        key: The object's key.
        rules: The parsed NOTIFY_RULES mapping of bucket name to a list of
               rule objects, each with a "name", a "prefix", and an optional
               list of "suffixes" (empty/absent means match any suffix).

    Returns:
        The names of every rule for this bucket whose prefix/suffixes match
        the given key. Empty if the bucket has no rules or none match.
    """
    matched = []

    for rule in rules.get(bucket, []):
        if not key.startswith(rule["prefix"]):
            continue

        suffixes = rule.get("suffixes") or []
        if suffixes and not any(key.endswith(suffix) for suffix in suffixes):
            continue

        matched.append(rule["name"])

    return matched


def build_notify_message(
    raw_record: dict,
    bucket: str,
    key: str,
    tributary_name: str | None,
    notification: str,
) -> dict:
    """Build the body of a data notification message for a matched rule.

    Args:
        raw_record: The raw S3 notification record for the object, used for
                    fields BucketNotificationRecord doesn't expose.
        bucket: The object's bucket.
        key: The object's key.
        tributary_name: The value of the TRIBUTARY_NAME environment variable.
        notification: The name of the matched notification rule.

    Returns:
        A dict ready to be JSON-serialized as the notify message body.
    """
    s3_object = raw_record.get("s3", {}).get("object", {})

    return {
        "schema_version": "1",
        "event_time": raw_record.get("eventTime"),
        "event_name": raw_record.get("eventName"),
        "bucket": bucket,
        "key": key,
        "size": s3_object.get("size"),
        "etag": s3_object.get("eTag"),
        "tributary": tributary_name,
        "notification": notification,
    }


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

    # data notification config is entirely optional/additive: when unset the
    # handler behaves exactly as it did before data notifications existed.
    notify_queue_name = os.getenv("NOTIFY_QUEUE_NAME")
    notify_rules_raw = os.getenv("NOTIFY_RULES")
    tributary_name = os.getenv("TRIBUTARY_NAME")

    notify_rules = None
    if notify_rules_raw:
        try:
            notify_rules = json.loads(notify_rules_raw)
        except ValueError as err:
            msg = f"NOTIFY_RULES is not valid JSON. {err}"
            return {"statusCode": 500, "body": msg}

    notify_queue_url = None

    try:
        # we'll bucket the incoming object infos and use them to send our
        # response if nothing fails miserably
        ignored_oi = []
        processed_oi = []

        # TODO: any other error checking here? we should get an exception if
        #       the response isn't valid...
        response = sqs_client.get_queue_url(QueueName=queue_name)
        queue_url = response["QueueUrl"]

        if notify_queue_name:
            notify_response = sqs_client.get_queue_url(
                QueueName=notify_queue_name
            )
            notify_queue_url = notify_response["QueueUrl"]

        for rec in event["Records"]:
            bucket_notif = BucketNotificationRecord(rec)

            # data notification path: independent of the ETL path below, and
            # a no-op unless NOTIFY_RULES has been configured for this
            # deployment.
            if notify_rules is not None:
                for notification in match_notify_rules(
                    bucket_notif.bucket, bucket_notif.key, notify_rules
                ):
                    qmsg = build_notify_message(
                        rec,
                        bucket_notif.bucket,
                        bucket_notif.key,
                        tributary_name,
                        notification,
                    )
                    group_id = derive_message_group_id(
                        bucket_notif.key,
                        tributary_name or notification or "notify",
                    )
                    try:
                        send_notify_message(
                            ddb_table, notify_queue_url, group_id, qmsg
                        )
                    except ClientError as err:
                        code, message = decode_error(err)
                        ddb_table.logger.exception(
                            "Failed to enqueue data notification for "
                            f"({bucket_notif.bucket}, {bucket_notif.key}); "
                            "continuing so the ETL path is unaffected. "
                            f"{code} {message}"
                        )

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
