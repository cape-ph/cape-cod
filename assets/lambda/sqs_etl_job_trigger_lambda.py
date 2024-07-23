"""Lambda function for kicking off Glue Jobs triggered from an SQS queue."""

import json

import boto3

# import os
# import urllib.parse

# from botocore.exceptions import ClientError

glue_client = boto3.client("glue")


# def requeue_message(event: dict):
#     """Requeue the SQS message that triggered this lambda.
#
#     This is needed if we attempt to start a glue job but don't have sufficient
#     concurrent runs available, or similar situations that keep us from running
#     right now, but do not preclude trying again later.
#
#     Args:
#         event: The event dict that comes into this lambda.
#
#     Raises:
#         ClientError: on inability to re-queue message.
#     """
#     sqs_client = boto3.client("sqs")
#
#     qarn = event["eventSourceARN"]
#     msg_groupid = event["MessageGroupId"]
#
#     # extract the queue name from the arn
#     _, _, qname = qarn.rpartition(":")
#
#     qurl = sqs_client.get_queue_url(QueueName=qname)
#
#     body = event["body"]
#
#     try:
#         sqs_client.send_message(
#             QueueUrl=qurl,
#             MessageBody=body,
#             MessageGroupId=msg_groupid,
#         )
#     except ClientError as err:
#         print(
#             f"Could not place message with body ({body}) on queue at URL "
#             f"({qurl}). {err.response['Error']['Code']} "
#             f"{err.response['Error']['Message']}"
#         )
#         raise err
#
#     print(f"Message ({body}) SUCCESSFULLY RE-QUEUED on queue at url ({qurl})")


def index_handler(event, context):
    """Handler for the object creation event on the Raw Epi/HAI data bucket.

    :param event: The event object that contains information about the object
                  that was created.
    :param context: Context object.
    """

    # if we get any of the following exceptions when we try to start a job, we
    # need to requeue the message we got triggered with and hope a future
    # execution can handle it successfully
    # requeue_exceptions = (
    #     glue_client.exceptions.InternalServiceException,
    #     glue_client.exceptions.OperationTimeoutException,
    #     glue_client.exceptions.ResourceNumberLimitExceededException,
    #     glue_client.exceptions.ConcurrentRunsExceededException,
    # )

    batch_item_failures = []
    successful_job_runs = []

    for rec in event["Records"]:
        # grab items from the incoming event needed later
        qmsg = json.loads(rec["body"])

        try:
            job_name = qmsg["etl_job"]
            bucket = qmsg["bucket"]
            obj_key = qmsg["key"]

            run_id = glue_client.start_job_run(
                JobName=job_name,
                Arguments={
                    "--RAW_BUCKET_NAME": bucket,
                    "--ALERT_OBJ_KEY": obj_key,
                },
            )
            status = glue_client.get_job_run(
                JobName=job_name, RunId=run_id["JobRunId"]
            )

            successful_job_runs.append(run_id["JobRunId"])

            print(f"Job Status : {status['JobRun']['JobRunState']}")

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
            batch_item_failures.append({"itemIdentifier": rec["messageId"]})

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

    # TODO:
    # - event format coming in contains our stuff in `body` (as a json dump)
    # - grab the `MessageGroupId` from the event in the event we need to requeue
    # - try to kick off the job. catch the error that is about too many
    #   concurrent jobs and re-queue in that case. (also see what other
    #   exceptions may happen)
    # - test all this stuff by uploading more objects than we have lambdas *and*
    #   concurrent jobs. need to make sure our requeuing works.
    #
    # EXCEPTIONS OF INTEREST FOR GLUE
    #   Glue.Client.exceptions.InvalidInputException
    #   Glue.Client.exceptions.EntityNotFoundException
    #   Glue.Client.exceptions.InternalServiceException
    #   Glue.Client.exceptions.OperationTimeoutException
    #   Glue.Client.exceptions.ResourceNumberLimitExceededException
    #   Glue.Client.exceptions.ConcurrentRunsExceededException

    # TODO this should be removed before any real deployment (dev is ok)
    # print(
    #     f"Received event: {json.dumps(event, indent=2)} with context {context}"
    # )
    #
    # return {
    #     "statusCode": 200,
    #     "body": f"MAYBE IN THE FUTURE I CAN START AN ETL JOB",
    # }

    # if glue_job_name is None:
    #     msg = "No glue job provided. Not starting a glue job"
    #     print(msg)
    #     return {"statusCode": 500, "body": msg}
    #
    # # the new object key that triggers the lambda is not known until now
    # # and cannot be obtained as an env var or parameter. needs to be
    # # grabbed from the event
    # # NOTE: the event structure for notifications can contain many records.
    # #       grabbin them all to handle potential of multiple uploads in a
    # #       batch. a new glue job will be started for each record
    # object_keys = [
    #     urllib.parse.unquote_plus(rec["s3"]["object"]["key"], encoding="utf-8")
    #     for rec in event["Records"]
    # ]
    #
    # try:
    #     for ok in object_keys:
    #         run_id = glue_client.start_job_run(
    #             JobName=glue_job_name,
    #             # NOTE: CLEAN_BUCKET_NAME is a default parameter the job will
    #             #       always run with
    #             Arguments={
    #                 "--RAW_BUCKET_NAME": raw_bucket_name,
    #                 "--ALERT_OBJ_KEY": ok,
    #             },
    #         )
    #         status = glue_client.get_job_run(
    #             JobName=glue_job_name, RunId=run_id["JobRunId"]
    #         )
    #         print(f"Job Status : {status['JobRun']['JobRunState']}")
    #         return {
    #             "statusCode": 200,
    #             "body": f"Glue job {glue_job_name} start successfully with JobRunId {status['JobRunId']}",
    #         }
    # except Exception as e:
    #     print(e)
    #     return {
    #         "statusCode": 500,
    #         "body": f"Glue job {glue_job_name} failed to start: {str(e)}",
    #     }
