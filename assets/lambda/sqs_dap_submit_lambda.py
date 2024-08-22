"""Lambda function for kicking off DAPs triggered from an SQS queue."""
import os
import json
import logging

import boto3

from botocore.exceptions import ClientError
logger = logging.getLogger(__name__)
# TODO: ISSUE #84

# TODO: ISSUE #87
ddb_resource = boto3.resource("dynamodb", region_name="us-east-2")


# TODO: ISSUE #86
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

# TODO: ISSUE #86
def get_dap_registry_table(table_name: str):
    """Get the DAP registry DynamoDB table by name.

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
        code, message = decode_error(err)

        if code == "ResourceNotFoundException":
            msg = (
                f"CAPE DAP registry DynamoDB table ({table_name}) could not"
                f"be found: {code} {message}",
            )
        else:
            msg = (
                f"Error trying to access CAPE data analysis pipeline registry "
                f"DynamoDB table ({table_name}): {code} {message}",
            )

        logger.error(msg)
        raise err

    return table

# TODO: ISSUE #86
def get_dap_registry_entry(table, pipeline_name: str, pipeline_version: str|None) -> dict | None:
    """Get the DAP registry entry for the given pipeline name from DynamoDB.

    Args:
        table: A reference to the DyanmoDB table.
        pipeline_name: The name of the pipeline who's registry entry we're
                       looking for.
        pipeline_version: The version of the pipeline who's registry entry we're
                       looking for. Optional and defaults to None

    Returns:
        A dict containing the registry entry if found.

    Raises:
        ClientError: If no table items can be found for the pipeline name.
    """
    ret = None
    try:
        k = {"pipeline_name": pipeline_name}

        # TODO: ISSUE #88
        if pipeline_version is not None:
            k.update({"version": pipeline_version})

        response = table.get_item(
            Key=k
        )

        ret = response["Item"]

    except ClientError as err:
        code, message = decode_error(err)

        logger.error(
            f"Couldn't get DAP registry entry for pipeline '{pipeline_name}'. "
            f"{code} {message}"
        )

    return ret

def index_handler(event, context):
    """Handler for the messages in the data analysis pipeline submit queue.

    :param event: The event object that contains SQS messages.
    :param context: Context object.
    """

    dap_registry_ddb_name = os.getenv("DAP_REG_DDB_TABLE")

    if dap_registry_ddb_name is None:
        msg = (
            "No DAP registry DynamoDB table name provided. Cannot submit DAP "
            "job to head node."
        )
        logger.error(msg)
        return {"statusCode": 500, "body": msg}

    batch_item_failures = []
    successful_dap_jobs = []
    invalid_dap_jobs = []

    # get a reference to the etl attributes table
    ddb_table = get_dap_registry_table(dap_registry_ddb_name)

    for rec in event["Records"]:
        # grab items from the incoming event needed later
        qmsg = json.loads(rec["body"])
        
        try:
            # TODO: ISSUE #84
            pipeline_name = qmsg["pipeline_name"]
            pipeline_version = qmsg["pipeline_version"]
            input_path = qmsg["input_path"]
            output_path = qmsg["output_path"]

            # attempt to get the registry entry from dynamodb. if we can't find
            # an entry, we'll log the error but not add to the batch failures
            # (if we can't find the entry, no amount of re-queing will help).

            dap_reg_entry = get_dap_registry_entry(
                ddb_table, pipeline_name, pipeline_version
            )

            if dap_reg_entry is None:
                logger.error(
                    f"Cannot find DAP registry entry for data analysis "
                    f"pipeline {pipeline_name} (version {pipeline_version}." 
                    "Cannot submit pipeline to the head node."
                )
                
                # add an entry to the invalid jobs list so we can add a count of
                # invalid jobs to the response
                invalid_dap_jobs.append((pipeline_name, pipeline_version))

                # back to the top of the loop
                continue
            else:
                logger.info(
                    f"Data analysis pipeline {pipeline_name} (version "
                    f"{pipeline_version} will be scheduled using input path "
                    f"[{input_path}] and output path [{output_path}]. The "
                    f"pipeline is of type {dap_reg_entry['pipeline_type']} "
                    "and will be sent to the appropriate head node."
                )

                # TODO: ISSUE #84 - when we submit the job to the (correct) head 
                #       node, hopefully there is some confirmation from the node 
                #       (with a run id or something) that we can store in 
                #       successful_dap_jobs for our return 200 message. until
                #       then we'll store a tuple of pipeline name/version just
                #       so we can get a count
                successful_dap_jobs.append((pipeline_name, pipeline_version))

        except Exception as e:
            # We are going to requeue the message on *any* exception in
            # processing
            print(
                f"Exception caught when starting data analysis pipeline: {e}. "
                f"Message will be requeued"
            )

            # TODO: ISSUE #89

            # we caught an exception that means we're not going to space today, but
            # could sometime in the future. so requeue the message hoping that day
            # will come.
            batch_item_failures.append({"itemIdentifier": rec["messageId"]})

    # check if we had any failures so we can update the queue as needed for
    # re-trigger
    if batch_item_failures:
        print(
            f"Some queue message processing resulted in errors. The following "
            f"message ids will be retried in the future: {batch_item_failures}"
        )
        return {"batchItemFailures": batch_item_failures}

    # if we got here, everything processed as expected and we can return a
    # success IFF we have successful jobs. if we have only invalids we'll return
    # a 400

    # we'll start by assuming the best and that all will be fine
    code = 200
    body = (
        f"Successfully submitted {len(successful_dap_jobs)} data "
        f"analysis pipeline jobs to the head node. "
        f"{len(invalid_dap_jobs)} were ignored."
    )
    
    # see if we only had invalids submitted and modify the response if so
    if not successful_dap_jobs and invalid_dap_jobs:
        code = 400

        body = (
            f"{len(successful_dap_jobs)} invalid data analysis pipeline "
            f"submissions encountered. Cannot submit any to the head node. "
        )

    # and respond
    return {
        "statusCode": code,
        "body": body,
    }
