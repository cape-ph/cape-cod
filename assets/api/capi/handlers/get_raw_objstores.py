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

        # TODO:
        # - determine if this will be run as the role returned from the
        #   authorizer.
        #   - if so, the code below may just work
        #   - if no:
        #       - check for Authorization header and make sure it's got a valid
        #         JWT. decode...
        #       - use the user to find the list of buckets and prefixes for the
        #         user
        # - make sure authorizer is handling 401/403

        resp_data = []
        bucket_paginator = s3_client.get_paginator("list_buckets")
        page_iter = bucket_paginator.paginate(
            PaginationConfig={"PageSize": 1000}
        )

        # first, get all the bucket names and make an empty prefixes list
        for page in page_iter:
            for bucket in page["Buckets"]:
                resp_data.append(
                    {
                        "objstore_name": bucket["Name"],
                        "prefixes": [],
                    }
                )

        # we have to do more API to get the objects/prefixes in the buckets.
        # can't do all this in one call.
        buckobj_paginator = s3_client.get_paginator("list_objects_v2")

        for rd in resp_data:
            page_iter = buckobj_paginator.paginate(
                Bucket=rd["objstore_name"], Delimiter="/"
            )

            # NOTE: the response contains a field called "CommonPrefixes", which
            #       is 100% what we want here *IFF* we're ok with a sinlge level
            #       of object key nesting (i.e. one `/` in the full object
            #       name). if we want more than one, this will have to change
            #       (and we may have even found that to be a problem with the
            #       lambda triggers). So for now we'll assume that to be the
            #       case
            for prefix in page_iter.search("CommonPrefixes"):
                if prefix is None:
                    print(f"{rd['objstore_name']} has no CommonPrefixes")
                    continue
                rd["prefixes"].append(prefix.get("Prefix"))

        # And return our response as a 200
        return {
            "statusCode": 200,
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
