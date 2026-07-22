"""Lambda function for listing the airflow workflow runs a user triggered.

This endpoint backs the "my workflows" view. It is a proxy to Airflow that
returns only the DAG runs whose `conf.cape.triggering_user_id` matches the
calling user, so the frontend does not have to track submitted runs client-side.

Ownership is recorded at trigger time by `post_workflow_run.py` (see
`conf.cape`), resolved from the API Gateway authorizer context.
"""

import json
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

# Keep in sync with post_workflow_run.CAPE_CONF_KEY.
CAPE_CONF_KEY = "cape"

# Page size when listing runs across all DAGs (Airflow caps page limit at 100).
DAG_RUNS_PAGE_LIMIT = 100
# Safety cap on how many recent runs we scan while filtering by owner. Airflow
# has no server-side filter for a `conf` value, so we page through the most
# recent runs and match `conf.cape` here.
MAX_RUNS_SCANNED = 1000


def caller_user_id(event):
    """Resolve the calling user's stable id.

    Prefers the identity injected by the API Gateway authorizer
    (`requestContext.authorizer.triggering_user_id`). Falls back to a `userId`
    query string parameter to support local/dev calls before the authorizer is
    fully wired.

    :param event: The API Gateway proxy event.
    :return: The user id string, or None if it cannot be resolved.
    """
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    user_id = authorizer.get("triggering_user_id")

    if not user_id:
        qsp = event.get("queryStringParameters") or {}
        user_id = qsp.get("userId")

    return str(user_id) if user_id else None


def run_belongs_to_user(run, user_id):
    """Return True if a DAG run was triggered by the given user.

    :param run: A single Airflow DAG run object (dict).
    :param user_id: The stable user id to match against `conf.cape`.
    """
    if not isinstance(run, dict) or not user_id:
        return False

    conf = run.get("conf")
    if not isinstance(conf, dict):
        return False

    cape = conf.get(CAPE_CONF_KEY)
    if not isinstance(cape, dict):
        return False

    return cape.get("triggering_user_id") == user_id


def filter_runs_for_user(runs, user_id):
    """Filter a list of DAG runs down to those triggered by the user.

    :param runs: Iterable of DAG run dicts.
    :param user_id: The stable user id to match against.
    :return: A list of matching runs (order preserved).
    """
    return [run for run in (runs or []) if run_belongs_to_user(run, user_id)]


def _list_all_dag_runs(mwaa_client, env_name):
    """List recent DAG runs across all DAGs, most recent first.

    Uses Airflow's cross-DAG list endpoint (`/dags/~/dagRuns/list`; the `~`
    wildcard means "all DAGs") so every DAG is covered by a single paginated
    stream instead of one request per DAG. Paging stops once MAX_RUNS_SCANNED
    runs have been seen or Airflow reports no more entries.
    """
    runs = []
    offset = 0

    while offset < MAX_RUNS_SCANNED:
        response = mwaa_client.invoke_rest_api(
            Name=env_name,
            Path="/dags/~/dagRuns/list",
            Method="GET",
            QueryParameters={
                "limit": DAG_RUNS_PAGE_LIMIT,
                "offset": offset,
                "order_by": "-logical_date",
            },
        )
        data = response["RestApiResponse"]
        page = data.get("dag_runs", [])
        runs.extend(page)

        offset += DAG_RUNS_PAGE_LIMIT
        if not page or offset >= data.get("total_entries", 0):
            break

    return runs


def index_handler(event, context):
    """Handler for GET of the calling user's workflow runs.

    Lists recent DAG runs across all DAGs in one paginated stream and returns
    only those triggered by the caller (matched on
    `conf.cape.triggering_user_id`).

    TODO: Airflow has no server-side filter for a `conf` value, so ownership
          filtering is done here after fetching recent runs. For large run
          volumes this should move to a database-backed ownership index (the
          CAPE environment DB).

    :param event: The event object that contains the HTTP request.
    :param context: Context object.
    """

    env_name = os.getenv("MWAA_ENVIRONMENT")

    # TODO: add this to capepy
    mwaa_client = boto3.client("mwaa")

    resp_headers = {
        "Content-Type": "application/json",
        # TODO: ISSUE #141 CORS bypass. We do not want this long term. See the
        #       other capi handlers for the full context on this.
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "OPTIONS,GET",
    }

    try:
        user_id = caller_user_id(event)

        if not user_id:
            # Without a resolvable caller we cannot scope the list. Return a 401
            # so the frontend can surface an auth problem rather than an empty
            # (and misleading) success.
            return {
                "statusCode": 401,
                "headers": resp_headers,
                "body": json.dumps(
                    {
                        "message": (
                            "Unable to resolve the calling user. A valid "
                            "Authorization token is required."
                        )
                    }
                ),
            }

        all_runs = _list_all_dag_runs(mwaa_client, env_name)
        matching_runs = filter_runs_for_user(all_runs, user_id)

        # Airflow already orders newest-first; sort defensively in case a page
        # boundary or backend quirk perturbs the order.
        matching_runs.sort(
            key=lambda run: run.get("logical_date") or "",
            reverse=True,
        )

        return {
            "statusCode": 200,
            "headers": resp_headers,
            "body": json.dumps(
                {
                    "dag_runs": matching_runs,
                    "total_entries": len(matching_runs),
                }
            ),
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = (
            f"Error during fetch of workflow runs from airflow. "
            f"{code} {message}"
        )

        return {
            "statusCode": 500,
            "body": msg,
        }
