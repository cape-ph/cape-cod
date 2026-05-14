"""Lambda function for handling a post to trigger an airflow dag."""

import datetime
import json
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error


def index_handler(event, context):
    """Handler for the POST to trigger an airflow dag.

    This endpoint is a proxy to the airflow /api/v2/dags/{dag_id}/dagRuns
    endpoint. Done as a lambda instead of direct integration so we can massage
    data as required.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    env_name = os.getenv("MWAA_ENVIRONMENT")

    # TODO: add this to capepy
    mwaa_client = boto3.client("mwaa")

    try:
        req_params = {"dagId"}

        qsp = event.get("queryStringParameters")

        if qsp is None:
            resp_data, resp_status = bad_param_response(list(req_params))
        else:
            dag_id = qsp.get("dagId")
            dag_params = json.loads(event["body"])

            if not dag_id:
                resp_data, resp_status = bad_param_response(list(req_params))
            else:

                # TODO: we can add some additional run params that airflow
                #       supports:
                #       - specific run id (probably don't want people using this
                #         usually if ever)
                #       - note (freetext string)
                #       - run_after (if we want to get into scheduling from
                #         users)
                #       - there are others like data_interval_[start|end] that
                #         are used internally in dags that process data of
                #         specific intervals
                request_params = {
                    "Name": env_name,
                    "Path": f"/dags/{dag_id}/dagRuns",
                    "Method": "POST",
                    "Body": {
                        "conf": dag_params,
                        "logical_date": datetime.datetime.now().isoformat(),
                    },
                }

                response = mwaa_client.invoke_rest_api(**request_params)

        # no matter the status code of the response we can return the same
        # thing. the difference in 200 vs non-200 is that the json will contain
        # an error string under the key "detail" instead of workflow data in
        # the non-200 case
        return {
            "statusCode": response["RestApiStatusCode"],
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
            "body": json.dumps(response["RestApiResponse"]),
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = f"Error during trigger of airflow dag run. {code} {message}"

        return {
            "statusCode": 500,
            "body": msg,
        }
