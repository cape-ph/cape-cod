"""Lambda function for kicking off Epi/HAI Glue Jobs."""

import json
import os
import urllib.parse

import boto3

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
    print(f"Received event: {json.dumps(event, indent=2)} with context {context}")

    if glue_job_name is None:
        msg = "No glue job provided. Not starting a glue job"
        print(msg)
        return {"statusCode": 500, "body": msg}

    # the new object key that triggers the lambda is not known until now
    # and cannot be obtained as an env var or parameter. needs to be
    # grabbed from the event
    # NOTE: the event structure for notifications can contain many records.
    #       grabbin them all to handle potential of multiple uploads in a
    #       batch. a new glue job will be started for each record
    object_keys = [
        urllib.parse.unquote_plus(rec["s3"]["object"]["key"], encoding="utf-8")
        for rec in event["Records"]
    ]

    try:
        for ok in object_keys:
            run_id = glue_client.start_job_run(
                JobName=glue_job_name,
                # NOTE: CLEAN_BUCKET_NAME is a default parameter the job will
                #       always run with
                Arguments={
                    "--RAW_BUCKET_NAME": raw_bucket_name,
                    "--ALERT_OBJ_KEY": ok,
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
