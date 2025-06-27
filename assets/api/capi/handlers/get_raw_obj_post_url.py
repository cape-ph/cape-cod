"""Lambda for handling GETs for S3 locations the authn'd user has access to."""

import json

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error


def index_handler(event, context):
    """Handler for the GET for S3 locations the authn'd user has access to.

    If there is no `Authorization` header present, this will return a 401.

    :param event: The event object that contains the HTTP request.
    :param context: Context object.
    """

    # Create an S3 client object
    s3_client = boto3.client("s3")

    try:

        headers = event.get("headers", {})

        resp_data = {}

        print(f"Event: {event}")
        print(f"Context: {context}")

        qsp = event.get("queryStringParameters", {})
        bucket = qsp.get("bucket")
        prefix = qsp.get("prefix")

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

        # TODO: in the future bucket should be set as a required param. prefix
        #       will not be not required
        if bucket is None:
            resp_data = {
                "message": "Missing required query string parameters: bucket"
            }
            resp_status = 400
        else:
            if prefix is not None:
                key = f"{prefix}/${{filename}}"
                conditions = [["starts-with", "$key", f"{prefix}/"]]
            else:
                key = "${filename}"
                conditions = []

            resp_data = s3_client.generate_presigned_post(
                Bucket=bucket,
                Key=key,
                ExpiresIn=3600,
                Fields=None,
                Conditions=conditions,
            )

        # And return our response however it ended up
        return {
            "statusCode": resp_status,
            "headers": resp_headers,
            "body": json.dumps(resp_data),
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = (
            f"Error during creation of URL for raw object POST. {code} "
            f"{message}"
        )

        return {
            "statusCode": 500,
            "body": msg,
        }
