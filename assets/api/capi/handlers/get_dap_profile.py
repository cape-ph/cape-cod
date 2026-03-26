"""Lambda function for handling a post of a new analysis pipeline run."""

import json
from decimal import Decimal

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


# TODO: this should probably go elsewhere. issue is you can't json serialize
#       Decimal values, and some of the values coming back from dynamo in the
#       pipeline profile spec are Decimal. So this shims them to floats.
def json_serialize_the_unserializable(val):
    """Serialze a value (e.g. Decimal) that is otherwise not json serializable.

    Right now this just handles Decimal, but can be updated as needed.

    :param val: The value to serialize.
    :return: the serialized value.
    :raises: TypeError if even this function cannot serialize.
    """
    if isinstance(val, Decimal):
        # this results in a reduction of precision which can cause issues. In
        # our case (for now at least) it's ok, but we may want to consider other
        # mechanisms like string conversions or forcing some rounding.
        return float(val)
    raise TypeError(f"Value {val} of type {type(val)} is not json serializable")


def index_handler(event, context):
    """Handler for the GET of the profile of a DAP version.

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
                    resp_data = dap["profile"]
                    print(f"resp_data: {resp_data}")
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
            "body": json.dumps(
                resp_data, default=json_serialize_the_unserializable
            ),
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
