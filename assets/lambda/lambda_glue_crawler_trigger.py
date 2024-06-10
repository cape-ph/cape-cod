"""Lambda function for kicking off a Glue Crawler."""

import json
import os
import time

import boto3

glue_client = boto3.client("glue")
max_retries = 10


def index_handler(event, context):
    """Handler for starting a glue crawler

    :param event: The event object that contains information about the object
                  that was created.
    :param context: Context object.
    """

    glue_crawler_name = os.getenv("GLUE_CRAWLER_NAME")

    # TODO this should be removed before any real deployment (dev is ok)
    print(f"Received event: {json.dumps(event, indent=2)} with context {context}")

    if glue_crawler_name is None:
        msg = "No glue crawler provided. Not crawling..."
        print(msg)
        return {"statusCode": 500, "body": msg}

    try:
        try_num = 0
        while (
            glue_client.get_crawler(Name=glue_crawler_name)["Crawler"]["State"]
            != "READY"
        ):
            try_num = try_num + 1
            time.sleep(60)
            if try_num > max_retries:
                msg = f"Maximum timeout reached waiting for {glue_crawler_name} to finish running"
                print(msg)
                return {"statusCode": 500, "body": msg}

        glue_client.start_crawler(Name=glue_crawler_name)
        return {"statusCode": 200, "body": f"Started crawling with {glue_crawler_name}"}
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": f"Glue job {glue_crawler_name} failed to start: {str(e)}",
        }
