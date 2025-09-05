"""Lambda function for handling a post of a new analysis pipeline run."""

import json

from botocore.exceptions import ClientError
from capepy.aws.dynamodb import PipelineTable
from capepy.aws.utils import decode_error


# TODO: need to add some abstraction of this to capepy. it's repeated here and
#       in get_object_etls at least
def bad_param_response():
    """Gets a response data object and status code when bad params are given.

    :return: A tuple containins a response data object and an HTTP 400 status
             code.
    """
    return (
        {
            "message": (
                "Missing required query string parameters: pipeline and version"
            )
        },
        400,
    )


def index_handler(event, context):
    """Handler for the GET of available profiles for a DAP version.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    try:
        headers = event.get("headers", {})

        qsp = event.get("queryStringParameters")

        if qsp is None:
            resp_data, resp_status = bad_param_response()
        else:
            pipeline_name = qsp.get("pipeline")
            version = qsp.get("version")

            if not pipeline_name or not version:
                resp_data, resp_status = bad_param_response()
            else:
                # get a reference to the registry table
                ddb_table = PipelineTable()

                dap = ddb_table.get_pipeline(pipeline_name, version)
                resp_data = []
                resp_status = 200
                if dap:
                    resp_data = [
                        {
                            "key": prof["key"],
                            "profileName": prof["display_name"],
                        }
                        for prof in dap["profiles"]
                    ]
        # And return our response as a 200
        return {
            "statusCode": resp_status,
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
