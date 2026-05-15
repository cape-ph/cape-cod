"""Lambda function for handling a patch to halt an airflow dag run."""

import datetime
import json
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import bad_param_response, decode_error


def index_handler(event, context):
    """Handler for the PATCH to halt an airflow dag run.

    This endpoint is a proxy to the airflow
    /api/v2/dags/{dag_id}/dagRuns/{dag_run_id} endpoint. Done as a lambda
    instead of direct integration so we can massage data as required.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    env_name = os.getenv("MWAA_ENVIRONMENT")

    # TODO: add this to capepy
    mwaa_client = boto3.client("mwaa")

    try:
        req_params = {"dagId", "dagRunId"}

        qsp = event.get("queryStringParameters")

        if qsp is None:
            resp_data, resp_status = bad_param_response(list(req_params))
        else:
            dag_id = qsp.get("dagId")
            dag_run_id = qsp.get("dagRunId")
            body = json.loads(event["body"])

            if not all([dag_id, dag_run_id]):
                resp_data, resp_status = bad_param_response(req_params)
            else:
                update_mask = ["state"]
                note = body.get("note")
                req_body = {"state": "failed"}

                if note:
                    update_mask.append("note")
                    req_body.update({"note": note})

                request_params = {
                    "Name": env_name,
                    "Path": f"/dags/{dag_id}/dagRuns/{dag_run_id}",
                    "Method": "PATCH",
                    "QueryParameters": {"update_mask": update_mask},
                    "Body": req_body,
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

        msg = (
            f"Error during halting/failing of airflow dag run. "
            f"{code} {message}"
        )

        return {
            "statusCode": 500,
            "body": msg,
        }
