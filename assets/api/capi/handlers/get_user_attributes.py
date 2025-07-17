"""Lambda for handling GETs for listing public user attributes."""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from capepy.aws.dynamodb import UserTable
from capepy.aws.utils import decode_error

logger = logging.getLogger()
logger.setLevel("INFO")


def index_handler(event, context):
    """Handler for the GET for listing public user attributes.

    If there is no `Authorization` header present, this will return a 401.

    :param event: The event object that contains the HTTP request.
    :param context: Context object.
    """

    try:

        headers = event.get("headers", {})

        resp_data = {}

        # assume the best will happen and set our output up for success
        resp_status = 200
        resp_headers = {
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
        }

        qsp = event.get("queryStringParameters")
        user_item = {}

        if qsp is None:
            resp_data = {
                "message": "Missing required query string parameters: userId"
            }
            resp_status = 400
        else:
            user_id = qsp.get("userId")

            # TODO: in the future bucket should be set as a required param. prefix
            #       will not be not required
            if user_id is None:
                resp_data = {
                    "message": "Missing required query string parameters: userId"
                }
                resp_status = 400
            else:
                # TODO: we can pair down the attributes returned with
                #       `ProjectionExpression`. We will probably want to make
                #       use of something like this to ensure only public attrs
                #       are returned

                ddb_table = UserTable()

                user_item = ddb_table.get_user(user_id)

                if user_item is None:
                    logger.warning(
                        "Attempt to get user attributes for non-existent user "
                        f"id: {user_id}"
                    )
                    # TODO: determine if a 404 is ok for both not found and
                    #       hidden (i.e. caller is not allowed to see). I assume
                    #       we'll have instances where a caller is asking for a
                    #       user they cannot query about.
                    resp_status = 404
                    msg = (
                        "User not found or caller doesn't have sufficient "
                        "permission to read user attributes."
                    )
                    user_item = {}
                else:
                    msg = f"Success"

                resp_data = {
                    "message": msg,
                    "attributes": user_item,
                }

        # And return our response however it ended up
        return {
            "statusCode": resp_status,
            "headers": resp_headers,
            "body": json.dumps(resp_data),
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = f"Error during fetch of user attributes. {code} " f"{message}"

        return {
            "statusCode": 500,
            "body": msg,
        }
