"""Lambda function for handling a post of a new analysis pipeline run."""

import json
import logging

import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

logger = logging.getLogger(__name__)


ec2_client = boto3.client("ec2")


def index_handler(event, context):
    """Handler for the GET of available ec2 instances to executing pipelines.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    try:
        # get all pipeline executor instances
        pipeline_executors = ec2_client.describe_instances(
            Filters=[
                {"Name": "instance-state-name", "Values": ["running"]},
            ]
        )

        # next, we really only want to return a few of the key/values for each
        # item. so extract what we want:
        resp_data = []
        for reservation in pipeline_executors.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                tags = {
                    tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])
                }
                if "Pipeline" in tags:
                    resp_data.append(
                        {
                            "instance_id": instance["InstanceId"],
                            "instance_name": tags.get("Name", None),
                            "pipeline_type": tags["Pipeline"],
                        }
                    )

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
            f"Error during processing of available ec2 instances for pipeline "
            f"execution. {code} {message}"
        )
        logger.exception(msg)

        return {
            "statusCode": 500,
            "body": msg,
        }
