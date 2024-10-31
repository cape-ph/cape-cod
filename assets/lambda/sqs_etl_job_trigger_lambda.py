"""Lambda function for kicking off Glue Jobs triggered from an SQS queue."""

import json

import boto3
from capepy.aws.lambda_ import ETLRecord

glue_client = boto3.client("glue")


def index_handler(event, context):
    """Handler for the object creation event on the Raw Epi/HAI data bucket.

    :param event: The event object that contains information about the object
                  that was created.
    :param context: Context object.
    """

    batch_item_failures = []
    successful_job_runs = []

    for rec in event["Records"]:
        # grab items from the incoming event needed later
        etl = ETLRecord(rec)

        try:
            print(
                f"Attempting to start etl job [{etl.job}] with bucket "
                f"[{etl.bucket}] and object key [{etl.key}]"
            )

            run_id = glue_client.start_job_run(
                JobName=etl.job,
                Arguments={
                    "--RAW_BUCKET_NAME": etl.bucket,
                    "--ALERT_OBJ_KEY": etl.key,
                },
            )
            status = glue_client.get_job_run(
                JobName=etl.job, RunId=run_id["JobRunId"]
            )

            successful_job_runs.append(run_id["JobRunId"])

            print(
                f"Success. Run ID {run_id['JobRunId']} Job Status : "
                f"{status['JobRun']['JobRunState']}"
            )

        except Exception as e:
            # We are going to requeue the message on *any* exception in
            # processing
            print(
                f"Exception caught when starting ETL job: {e}. Message will "
                "be requeued"
            )

            # TODO: we may want to consider a dead letter queue to keep from
            #       getting into a case where there are a ton of new objects
            #       (file) uploaded by users for a long period of time, which
            #       would likely outstrip our number of concurrent glue job
            #       runs, which would lead to a number of re-queued messages
            #       that will trigger lambda at the same time that a bunch of
            #       new objects is also triggering lambda. can lead to a
            #       "snowball" (anti)pattern. See here:
            # https://docs.aws.amazon.com/prescriptive-guidance/latest/lambda-event-filtering-partial-batch-responses-for-sqs/best-practices-partial-batch-responses.html#snowball-anti-patterns

            # we caught an exception that means we're not going to space today, but
            # could sometime in the future. so requeue the message hoping that day
            # will come.
            batch_item_failures.append({"itemIdentifier": etl.id})

    # check if we had any failures so we can update the queue as needed for
    # re-trigger
    if batch_item_failures:
        print(
            f"Some queue message processing resulted in errors. The following "
            f"message ids will be retried in the future: {batch_item_failures}"
        )
        return {"batchItemFailures": batch_item_failures}

    # if we got here, everything processed as expected and we can return a
    # success
    return {
        "statusCode": 200,
        "body": (
            f"Successfully started {len(successful_job_runs)} ETL jobs. Job IDs: "
            f"{successful_job_runs}."
        ),
    }
