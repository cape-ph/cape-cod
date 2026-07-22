"""Lambda function for handling a post to trigger an airflow dag."""

import datetime
import json
import os
import re

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import bad_param_response, decode_error

# Namespace under the DAG run `conf` where CAPE-owned metadata lives, kept
# separate from the DAG's own parameters so the two never collide.
CAPE_CONF_KEY = "cape"


def caller_identity_from_event(event):
    """Read the caller identity injected by the API Gateway authorizer.

    The authorizer resolves the Cognito user and passes it in the request
    context. We only trust this server-side value for ownership; we never trust
    identity sent in the request body.

    :param event: The API Gateway proxy event.
    :return: A dict with any of `triggering_user_id` / `triggering_user_name`.
    """
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}

    identity = {}
    user_id = authorizer.get("triggering_user_id")
    if user_id:
        identity["triggering_user_id"] = str(user_id)

    user_name = authorizer.get("triggering_user_name")
    if user_name:
        identity["triggering_user_name"] = str(user_name)

    return identity


def apply_cape_identity(conf, identity):
    """Stamp the resolved caller identity onto a DAG run `conf`.

    Any client-supplied `cape` block is removed first so a caller cannot forge
    ownership. When no identity is available (e.g. authorizer not yet resolving
    users) the `cape` block is simply absent.

    :param conf: The DAG run conf dict (the passthrough of the request body).
    :param identity: The identity dict from `caller_identity_from_event`.
    :return: The same conf dict, mutated in place and returned for convenience.
    """
    if not isinstance(conf, dict):
        return conf

    # Never allow client-provided CAPE metadata through.
    conf.pop(CAPE_CONF_KEY, None)

    if identity:
        conf[CAPE_CONF_KEY] = dict(identity)

    return conf


def index_handler(event, context):
    """Handler for the POST to trigger an airflow dag.

    This endpoint is a proxy to the airflow /api/v2/dags/{dag_id}/dagRuns
    endpoint. Done as a lambda instead of direct integration so we can massage
    data as required.

    In addition to forwarding the request body as the DAG run `conf`, this
    handler stamps the triggering user (resolved by the API Gateway authorizer)
    into `conf.cape` so ownership is recorded in Airflow state, visible in the
    Airflow UI, and retrievable via the Airflow API.

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

                # Stamp the triggering user (from the authorizer context) into
                # the conf. Client-supplied `cape` metadata is stripped so
                # ownership cannot be spoofed.
                identity = caller_identity_from_event(event)
                dag_params = apply_cape_identity(dag_params, identity)

                # TODO: we can add some additional run params that airflow
                #       supports:
                #       - specific run id (probably don't want people using this
                #         usually if ever)
                #       - run_after (if we want to get into scheduling from
                #         users)
                #       - there are others like data_interval_[start|end] that
                #         are used internally in dags that process data of
                #         specific intervals

                # the logical date must be specified (but may be null) when
                # triggering. we're specifying the value. *but* it wants ISO
                # 8601 format ending in `Z` which isn't supported in python
                # natively till v3.11. so this makes the time string then
                # replaces the bad part with `Z` so the airflow api accepts it.
                now_str = datetime.datetime.now().isoformat()
                zstr = re.sub(r"\..*$", "Z", now_str)

                body = {
                    "conf": dag_params,
                    "logical_date": zstr,  # datetime.datetime.now().isoformat(),
                }

                # Surface the triggering user in the run `note` too, so admins
                # scanning the Airflow runs list can see it without opening conf.
                user_name = identity.get(
                    "triggering_user_name"
                ) or identity.get("triggering_user_id")
                if user_name:
                    body["note"] = f"Triggered by {user_name}"

                request_params = {
                    "Name": env_name,
                    "Path": f"/dags/{dag_id}/dagRuns",
                    "Method": "POST",
                    "Body": body,
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

        msg = f"Error during trigger of airflow dag run. {code} {message}"

        return {
            "statusCode": 500,
            "body": msg,
        }
