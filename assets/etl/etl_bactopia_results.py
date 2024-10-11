"""ETL script for the initial subset of bactopia results we'll handle."""

import csv
import io
import os.path
import re
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

# partition/column name
BACTRUN_PARTITION = "bactopia_run"
# the files of interest (needed to handle each differently)
MLST_OBJ = "mlst.tsv"
# the versions of the bactopia toolchain seem to have different names of this
# file in the output. this could be a bactopia or amrfinder plus reason, but the
# amrfinderplus file from bactopia version 3.0.1 (and maybe before???) has
# `-protiens` and later versions (at least 3.1.0+) don't.
AMRF_OBJ_301 = "amrfinderplus-proteins.tsv"
AMRF_OBJ_31X = "amrfinderplus.tsv"

# TODO: These are the keys we care about matching and processing right now.
#       this is not exhaustive in the long term and really only supports
#       our current single run use case of bactopia.

# these names are looked for explicitly if the object is in the bactopia output
# hierarchy
BACTRUN_KEYS = (
    # different versions of the bactopia tool chainss have different names for
    # the amr finder files it seems
    f"merged-results/{AMRF_OBJ_301}",
    f"merged-results/{AMRF_OBJ_31X}",
    f"merged-results/{MLST_OBJ}",
)


# TODO: ISSUE #144 the output here is for the initial bactopia
#       data handling only (and is specific to a particular invocation of
#       bactopia that is not the only way we care about). It is by no means
#       something that must be carried forward if there is a better way

# before anything else, make sure this object key is one we care about
# and if so grab all the parts of it we need
process_object = False
prefix = None
objfull = None
objname = None
suffix = None


if alert_obj_key.endswith(BACTRUN_KEYS):
    # in the case of bactopia output files, we'll want the first 2 parts of
    # the original prefix (e.g. 'bactopia-runs/bactopia-20241008-183748/')
    # and the object name sith suffix. conveniently this means we can just
    # split on "merged-results/"
    prefix, objfull = alert_obj_key.split("merged-results/")
    _, prefix = prefix.split("bactopia-runs/")
    # if we have an old named amrfinder plus file, rename the output name to be
    # the asme as the newer ones
    objname, suffix = objfull.split(".")
    objname = (
        re.sub(r"-.*", "", objname) if objname == AMRF_OBJ_301 else objname
    )


# we should have no missing values here
if not all([prefix, objfull, objname, suffix]):
    print(f"Bactopia output ETL ignoring {alert_obj_key} per configuration.")
    # TODO: this shows the job as failed AWS console. need this to still be able
    #       to be considered a success.
    sys.exit(0)

# NOTE: May need some creds here
s3_client = boto3.client("s3")


# NOTE: f"{var}" here is to make the LSP happy. it's convinced they could
#       be None, which would cause us to exit this job prior to here. but
#       whatevs...
clean_obj_key = os.path.join(
    f"{objname}", f"{BACTRUN_PARTITION}={prefix}", f"{objname}.csv"
)

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
    reader = csv.reader(
        io.StringIO(response.get("Body").read().decode("utf-8")), delimiter="\t"
    )

    # NOTE: based on file name matching above, we should never end up where an
    #       if/elif is not hit here
    if objfull == "MLST_OBJ":
        # in the mlst.tsv case, we have no header row and need to provide our
        # own
        print(f"Processing MLST file (raw key: {alert_obj_key})")

        # TODO: these headers are made up except for the first 3. this will
        #       need to be fixed sometime if we keep processing this file
        writer.writerow(
            [
                "sample",
                "scheme",
                "sequence_type",
                *[f"gene{i}" for i in range(7)],
            ]
        )
        writer.writerows([row for row in reader])

    elif objfull in [AMRF_OBJ_301, AMRF_OBJ_31X]:
        print(f"Processing AMRFinderPlus file (raw key: {alert_obj_key})")
        # in this case we need to grab the header and modify it to replace
        # spaces and dashes with underscores, and lowercase everything
        for idx, row in enumerate(reader):
            if idx == 0:
                # TODO: ISSUE #TBD ETL helper library needs a normalization
                #       function for column headers to do this...

                # special processing of the columns
                row = [re.sub(r"[\s-]", "_", c).lower() for c in row]

            writer.writerow(row)

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
