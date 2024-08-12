"""Lambda function for handling a post of a new analysis pipeline run."""

import json


def index_handler(event, context):
    """Handler for the POST of a new analysis pipeline run.

    :param event: The event object that contains the HTTP request and json
                  data.
    :param context: Context object.
    """

    # TODO this should be removed before any real deployment (dev is ok)
    print(
        f"Analysis Pipeline API (POST new pipeline run) received event: "
        f"{json.dumps(event, indent=2)} with context {context}"
    )

    try:
        body = json.loads(event["body"])

        pipeline_name = body["pipelineName"]
        pipeline_version = body["pipelineVersion"]
        input_path = body["inputPath"]
        output_path = body["outputPath"]

        msg = (
            f"Data analsysis pipeline {pipeline_name} (version "
            f"{pipeline_version} will be scheduled using input path "
            f"[{input_path}] and output path [{output_path}]"
        )

        print(msg)

        return {
            "statusCode": 200,
            "body": msg,
        }
    except KeyError as ke:
        msg = f"Required value {ke.args[0]} is missing. event: [{event}]"
        print(
            f"Exception caught when processing json payload. {msg}. Error: {ke}"
        )
        return {
            "statusCode": 400,
            "body": msg,
        }
