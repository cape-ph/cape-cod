"""ETL script for the initial subset of bactopia results we'll handle."""

import csv
import io
import os.path
import sys

import boto3 as boto3
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

# TODO: These are the keys we care about matching and processing right now.
#       this is not exhaustive in the long term and really only supports
#       our current single run use case of bactopia.

# these names are looked for explicitly if the object is in the bactopia output
# hierarchy
bactrun_keys = (
    # different versions of the bactopia tool chainss have different names for
    # the amr finder files it seems
    "merged-results/amrfinderplus-proteins.tsv",
    "merged-results/amrfinderplus.tsv",
    "merged-results/mlst.tsv",
)

# TODO:
# - pair down the input file set. too many jobs
# - make sure the key matches the bactrun key if in bactopia_runs (and grab the
#   run id if so)
# - make sure the key matches the regex if not in bactopia_runs (and grab the
#   pathogen id if so)
# - test by copying only those files
# - if that works, convert each to csv. write to clean are in either
#   `bactopia-runs/run_id` or `pathogen_id/`
# - check the crawler is doing its thing

# before anything else, make sure this object key is one we care about
process_object = False
# TODO: WIP, may not be smartest thing...
prefix = None
# TODO: may not actually need this except in filename processing below...
objfull = None
objname = None
suffix = None

if alert_obj_key.endswith(bactrun_keys):
    # in the case of bactopia output files, we'll want the first 2 parts of
    # the original prefix (e.g. 'bactopia-runs/bactopia-20241008-183748/')
    # and the object name sith suffix. conveniently this means we can just
    # split on "merged-results/"
    prefix, objfull = alert_obj_key.split("merged-results/")
    _, prefix = prefix.split("bactopia-runs/")
    objname, suffix = objfull.split(".")

# we should have no missing values here
if not all([prefix, objfull, objname, suffix]):
    print(f"Bactopia output ETL ignoring {alert_obj_key} per configuration.")
    # TODO: this shows the job as failed AWS console. need this to still be able
    #       to be considered a success.
    sys.exit(0)

# NOTE: May need some creds here
s3_client = boto3.client("s3")

# TODO: ISSUE #144 the output here is for the initial bactopia
#       data handling only and is by no means something that must be carried
#       forward, but for now we are writing the transformed data to the same
#       bucket as the pre-transform data (in a different prefix) so we want a
#       way to carry around the prefix to write to (which we don't have
#       currently)

# all output objects will be csv files for now
# NOTE: f"{prefix}" here is to make the LSP happy. it's convinced prefix could
#       be None, which would cause us to exit this job prior to here. but
#       whatevs...
clean_obj_key = os.path.join(f"{prefix}", f"{objname}.csv")

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
print(f"Processing new object: {alert_obj_key}")

# TODO: the only real special case here is the mlst.tsv file which has no column
#       headers. otherwise we're really just going to copy the file over to a
#       new path with a new suffix
with io.StringIO() as sio_buff:
    writer = csv.writer(sio_buff)
    if objfull == "mlst.tsv":
        # in the mlst.tsv case, we have not header row and need to provide our
        # own

        # TODO: these headers are made up except for the first 3. this will need
        # to be fixed sometime if we keep processing this file
        writer.writerow(
            [
                "sample",
                "scheme",
                "sequence type",
                *[f"gene{i}" for i in range(7)],
            ]
        )

    reader = csv.reader(
        io.StringIO(response.get("Body").read().decode("utf-8")), delimiter="\t"
    )
    writer.writerows(row for row in reader)

    response = s3_client.put_object(
        Bucket=clean_bucket_name, Key=clean_obj_key, Body=sio_buff.getvalue()
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
