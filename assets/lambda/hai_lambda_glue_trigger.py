"""Lambda function for kicking off Epi/HAI Glue Jobs."""

import json
import os

import boto3
from capepy.aws.lambda_ import BucketNotificationRecord

glue_client = boto3.client("glue")


def index_handler(event, context):
    """Handler for the object creation event on the Raw Epi/HAI data bucket.

    :param event: The event object that contains information about the object
                  that was created.
    :param context: Context object.
    """

    glue_job_name = os.getenv("GLUE_JOB_NAME")
    raw_bucket_name = os.getenv("RAW_BUCKET_NAME")

    # TODO this should be removed before any real deployment (dev is ok)
    print(
        f"Received event: {json.dumps(event, indent=2)} with context {context}"
    )

    if glue_job_name is None:
        msg = "No glue job provided. Not starting a glue job"
        print(msg)
        return {"statusCode": 500, "body": msg}

    try:
        for rec in event["Records"]:
            run_id = glue_client.start_job_run(
                JobName=glue_job_name,
                # NOTE: CLEAN_BUCKET_NAME is a default parameter the job will
                #       always run with
                Arguments={
                    "--RAW_BUCKET_NAME": raw_bucket_name,
                    "--OBJECT_KEY": BucketNotificationRecord(rec).key,
                },
            )
            status = glue_client.get_job_run(
                JobName=glue_job_name, RunId=run_id["JobRunId"]
            )
            print(f"Job Status : {status['JobRun']['JobRunState']}")
            return {
                "statusCode": 200,
                "body": f"Glue job {glue_job_name} start successfully with JobRunId {status['JobRunId']}",
            }
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": f"Glue job {glue_job_name} failed to start: {str(e)}",
        }
