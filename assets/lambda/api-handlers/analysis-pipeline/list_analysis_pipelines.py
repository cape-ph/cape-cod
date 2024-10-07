"""Lambda function for handling a post of a new analysis pipeline run."""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


ddb_resource = boto3.resource("dynamodb", region_name=os.getenv("DDB_REGION"))


# TODO: ISSUE #86
def decode_error(err: ClientError):
    """Decode a ClientError from AWS.

    Args:
        err: The ClientError being decoded.

    Returns:
        A tuple containing the error code and the error message provided by AWS.
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


def index_handler(event, context):
    """Handler for the POST of a new analysis pipeline run.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    dap_registry_ddb_name = os.getenv("DAP_REG_DDB_TABLE")

    if dap_registry_ddb_name is None:
        msg = (
            "No DAP registry DynamoDB table name provided. Cannot list "
            "available data analysis pipelines."
        )
        logger.error(msg)
        return {"statusCode": 500, "body": msg}

    try:
        # get a reference to the registry table
        ddb_table = get_dap_registry_table(dap_registry_ddb_name)

        # as we're returning all available pipelines in the registry, we need to
        # scan the whole table. scan is limited to 1MB return data, which won't be a
        # problem till we have a lot of pipelines, but we'll include the pagination
        # loop we'll need for future proofing
        response = ddb_table.scan()
        pipeline_records = response["Items"]

        while "LastEvaluatedKey" in response:
            response = ddb_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            pipeline_records.extend(response["Items"])

        # next, we really only want to return a few of the key/values for each
        # item. so extract what we want:
        keys = ("pipeline_name", "pipeline_type", "version")
        resp_data = [dict((k, r[k]) for k in keys) for r in pipeline_records]

        # And return our response as a 200
        return {
            "statusCode": 200,
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
                "Access-Control-Allow-Methods": "OPTIONS,GET",
            },
            "body": json.dumps(resp_data),
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
