"""Lambda function for handling a get of an airflow workflow run."""

import json
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import bad_param_response, decode_error


def index_handler(event, context):
    """Handler for the GET all tasks for an airflow workflow DAG.

    This endpoint is a proxy to the airflow /api/v2/dags/{dag_id}/tasks
    endpoints. Done as a lambda instead of direct integration so we can
    massage data as required.

    This endpoint does not return any CAPE specific data such as the pipeline
    profiles of the pipelines in the workflows. That is a separate API call.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    env_name = os.getenv("MWAA_ENVIRONMENT")

    # TODO: add this to capepy
    mwaa_client = boto3.client("mwaa")

    req_params = {"dagId"}

    try:
        qsp = event.get("queryStringParameters")

        if qsp is None:
            resp_data, resp_status = bad_param_response(list(req_params))
        else:
            dag_id = qsp.get("dagId")

            if dag_id is None:
                resp_data, resp_status = bad_param_response(list(req_params))

            else:
                api_path = f"/dags/{dag_id}/tasks"

                request_params = {
                    "Name": env_name,
                    "Path": api_path,
                    "Method": "GET",
                }

                response = mwaa_client.invoke_rest_api(**request_params)
                resp_data = response["RestApiResponse"]
                resp_status = response["RestApiStatusCode"]

        # no matter the status code of the response we can return the same
        # thing. the difference in 200 vs non-200 is that the json will contain
        # an error string under the key "detail" instead of workflow data in
        # the non-200 case
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
            f"Error during fetch of workflow run data from airflow. "
            f"{code} {message}"
        )

        return {
            "statusCode": 500,
            "body": msg,
        }
