"""ETL script for the initial subset of bactopia results we'll handle."""

import io
import os.path
import sys

import boto3 as boto3
import pandas as pd
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyspark.sql import SparkSession

# for our purposes here, the spark and glue context are only (currently) needed
# to get the logger.
spark_ctx = SparkSession.builder.getOrCreate()  # pyright: ignore
glue_ctx = GlueContext(spark_ctx)
logger = glue_ctx.get_logger()

parameters = getResolvedOptions(
    sys.argv,
    [
        "RAW_BUCKET_NAME",
        "ALERT_OBJ_KEY",
        "CLEAN_BUCKET_NAME",
    ],
)

# TODO: ISSUE #150 we should change our generic etl concept to not use the
#       words "raw" or "alert". probably not even "clean". Then we can get
#       to a place where we can reuse things outside the raw/clean alert
#       etl paradigm.

raw_bucket_name = parameters["RAW_BUCKET_NAME"]
alert_obj_key = parameters["ALERT_OBJ_KEY"]
clean_bucket_name = parameters["CLEAN_BUCKET_NAME"]

# NOTE: May need some creds here
s3_client = boto3.client("s3")

# TODO: ISSUE #144 the `transformed-results` here is for the initial bactopia
#       data handling only and is by no means something that must be carried
#       forward, but for now we are writing the trasformed data to the same
#       bucket as the pre-transform data (in a different prefix) so we want a
#       way to carry around the prefix to write to (which we don't have
#       currently)
clean_obj_key = os.path.join("transformed-results", alert_obj_key)

# try to get the object from S3 and handle any error that would keep us
# from continuing.
response = s3_client.get_object(Bucket=raw_bucket_name, Key=alert_obj_key)

status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")

if status != 200:
    err = (
        f"ERROR - Could not get object {alert_obj_key} from bucket "
        f"{raw_bucket_name}. ETL Cannot continue."
    )

    logger.error(err)

    # NOTE: need to properly handle exception stuff here, and we probably want
    #       this going somewhere very visible (e.g. SNS topic or a perpetual log
    #       as someone will need to be made aware)
    raise Exception(err)

logger.info(f"Obtained object {alert_obj_key} from bucket {raw_bucket_name}.")

# handle the document itself...

# TODO: ISSUE #151 we don't know what we're doing with these results yet, so
#       for now we'll just write the input file to the output location

# write out the transformed data
with io.StringIO() as sio_buff:

    response = s3_client.put_object(
        Bucket=clean_bucket_name,
        Key=clean_obj_key,
        Body=response.get("Body").read(),
    )

    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")

    if status != 200:
        err = (
            f"ERROR - Could not write transformed data object {clean_obj_key} "
            f"to bucket {clean_bucket_name}. ETL Cannot continue."
        )

        logger.error(err)

        # NOTE: need to properly handle exception stuff here, and we probably
        #       want this going somewhere very visible (e.g. SNS topic or a
        #       perpetual log as someone will need to be made aware)
        raise Exception(err)

    logger.info(
        f"Transformed {raw_bucket_name}/{alert_obj_key} and wrote result "
        f"to {clean_bucket_name}/{clean_obj_key}"
    )
