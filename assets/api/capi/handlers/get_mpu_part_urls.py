"""Lambda for handling GETs for S3 locations the authn'd user has access to."""

import json

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error


def index_handler(event, context):
    """Handler for the GET for a list of S3 multipart upload part URLs.

    :param event: The event object that contains the HTTP request.
    :param context: Context object.
    """

    # Create an S3 client object
    s3_client = boto3.client("s3")

    try:

        headers = event.get("headers", {})

        print(f"Event: {event}")
        print(f"Context: {context}")

        qsp = event.get("queryStringParameters", {})
        bucket = qsp.get("bucket")
        key = qsp.get("key")
        upload_id = qsp.get("uploadId")
        num_parts = int(qsp.get("numParts"))

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

        resp_data = []

        if None in [bucket, key, upload_id, num_parts]:
            resp_data = {
                "message": (
                    "Missing required query string parameter(s): bucket, key, "
                    "uploadId and/or numparts"
                )
            }
            resp_status = 400
        else:
            # part numbering is any increasing set of values on 1...10000. We're
            # just going 1 to num_parts+1 cause easy
            for i in range(1, num_parts + 1):
                put_url = s3_client.generate_presigned_url(
                    ClientMethod="upload_part",
                    Params={
                        "Bucket": bucket,
                        "Key": key,
                        "UploadId": upload_id,
                        "PartNumber": i,
                    },
                    # TODO: need to make this more resilient. perhaps something
                    #       where the system is configured with a max allowed
                    #       epiration and a default expiration. The client can
                    #       ask for any exiration seconds, but can get no more
                    #       than the max allowed (the value ultimately set
                    #       would need to be returned in the results)
                    # hard-coded 8 hours for now
                    ExpiresIn=28800,
                )
                resp_data.append({"url": put_url, "partNumber": i})

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
