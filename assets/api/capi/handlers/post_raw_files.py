"""Lambda function for handling a post of a new analysis pipeline run."""

import json
import logging
import os

import boto3
import multipart
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

logger = logging.getLogger(__name__)


def index_handler(event, context):
    """Handler for the POST of a set of raw files to be added to object storage.

    :param event: The event object that contains the HTTP request and form
                  data.
    :param context: Context object.
    """

    # Create an S3 client object
    s3_client = boto3.client("s3")

    try:
        headers = {k.lower(): v for k, v in event["headers"].items()}
        body = base64.b64decode(event["body"])

        # the multipart library likes a very specific wsgi environ dict format,
        # so make one to keep it happy...
        environ = {
            "CONTENT_LENGTH": headers["content-length"],
            "CONTENT_TYPE": headers["content-type"],
            "REQUEST_METHOD": "POST",
            "wsgi.input": BytesIO(body),
        }
        form, files = multipart.parse_form_data(environ)
        form_data = dict(form)

        # TODO: remove prints that houldn't go to prod
        print(f"posting raw data file with form data: {form_data}")

        objstore_name = form_data["objstore_name"]
        prefix = form_data["prefix"]

        for key, f in files.items():
            objkey = f"{prefix}/{f.name}"
            print(f"Handling uploaded file: {objkey} (upload key: {key})")
            s3_client.put_object(
                Bucket=objstore_name,
                Key=objkey,
                Body=f.file,
            )

        return {
            "statusCode": 200,
            "body": "Files uploaded successfully",
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
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            },
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = f"Error during processing of raw uploaded files. {code} {message}"
        print(msg)

        return {
            "statusCode": 500,
            "body": msg,
        }
