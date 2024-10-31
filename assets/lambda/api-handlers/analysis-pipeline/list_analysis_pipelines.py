"""Lambda function for handling a post of a new analysis pipeline run."""

import json

from botocore.exceptions import ClientError
from capepy.aws.dynamodb import PipelineTable
from capepy.aws.utils import decode_error


def index_handler(event, context):
    """Handler for the GET of all available analysis pipelines.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    try:
        # get a reference to the registry table
        ddb_table = PipelineTable()

        # as we're returning all available pipelines in the registry, we need to
        # scan the whole table. scan is limited to 1MB return data, which won't be a
        # problem till we have a lot of pipelines, but we'll include the pagination
        # loop we'll need for future proofing
        response = ddb_table.table.scan()
        pipeline_records = response["Items"]

        while "LastEvaluatedKey" in response:
            response = ddb_table.table.scan(
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

        return {
            "statusCode": 500,
            "body": msg,
        }
