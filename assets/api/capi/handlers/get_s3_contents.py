"""Lambda for handling GETs for S3 contents the authn'd user has access to."""

import json

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error


def bad_param_response():
    """Gets a response data object and status code when bad params are given.

    :return: A tuple containins a response data object and an HTTP 400 status
             code.
    """
    return (
        {"message": ("Missing required query string parameters: bucket")},
        400,
    )


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

        ### LEFTOFF
        # TODO:
        # - pull out bucket name and (optional) prefix. handler errors
        # - query for contents of said bucket/prefix with boto3
        # - add todos for authz/opa
        # - ensure list bucket contents perms are on the api

        qsp = event.get("queryStringParameters")

        if qsp is None:
            resp_data, resp_status = bad_param_response()
        else:
            bucket = qsp.get("bucket")
            prefix = qsp.get("prefix")

            # TODO: in the future bucket should be set as a required param. prefix
            #       will not be not required
            if not bucket:
                resp_data, resp_status = bad_param_response()
            else:
                buckobj_paginator = s3_client.get_paginator("list_objects_v2")

                # NOTE: if you pass `Delimiter` here all you get back is
                #       prefixes names (and not the contents of those prefixes
                page_iter = buckobj_paginator.paginate(
                    Bucket=bucket, Prefix=prefix or ""
                )

                bucket_objects = []

                for page in page_iter:
                    if "Contents" not in page:
                        # this will happen if there are no objects (at all or in
                        # a specified prefix). also catches if a bad prefix is
                        # given
                        continue

                    for bobj in page["Contents"]:
                        # TODO: we'll eventually want more than the object name
                        #       here probs. otherwise this would just be a list
                        #       comp
                        bucket_objects.append(bobj["Key"])

                resp_status = 200
                resp_data = {
                    "bucket": bucket,
                    "objects": bucket_objects,
                }

        # And return our response
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
            f"Error during fetch of object storage locations for user. {code} "
            f"{message}"
        )

        return {
            "statusCode": 500,
            "body": msg,
        }
