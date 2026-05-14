"""Lambda function for handling a get of pipeline profiles used in a workflow."""

import json

from botocore.exceptions import ClientError
from capepy.aws.dynamodb import PipelineTable, WorkflowMetaTable
from capepy.aws.utils import (
    bad_param_response,
    decode_error,
    json_serialize_the_unserializable,
)


def index_handler(event, context):
    """Handler for the GET of the profiles used in a workflow (airflow dag).

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    req_params = {"dagId"}

    try:
        headers = event.get("headers", {})

        qsp = event.get("queryStringParameters")

        if qsp is None:
            resp_data, resp_status = bad_param_response(list(req_params))
        else:
            dag_id = qsp.get("dagId")

            if dag_id is None:
                resp_data, resp_status = bad_param_response(list(req_params))
            else:

                workflow_table = WorkflowMetaTable()
                wf = workflow_table.get_workflow_by_id(dag_id)

                # get a reference to the registry table
                dapreg_table = PipelineTable()
                resp_data = []
                resp_status = 200

                if wf is None:
                    resp_data = [
                        {"detail": f"Could not find workflow with id {dag_id} "}
                    ]
                    resp_status = 404
                else:
                    for pid in wf["pipeline_ids"]:
                        dap = dapreg_table.get_pipeline(pid)
                        if dap:
                            resp_data.append(dap["profile"])
                        else:
                            # TODO: What other errors to handle here?
                            resp_data = [
                                {
                                    "detail": f"Could not find pipeline profile for pipeline with id {pid} "
                                }
                            ]
                            resp_status = 404
                            break

        # And return our response however it worked out
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
            f"Error during fetch of workflow pipeline profiles. "
            f"{code} {message}"
        )

        return {
            "statusCode": 500,
            "body": msg,
        }
