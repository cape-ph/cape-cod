"""ETL script for raw Epi/HAI CRE alert docx."""

import io
import sys

import boto3 as boto3
import dateutil.parser as dparser
import pandas as pd
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from docx import Document
from pyspark.sql import SparkSession

# for our purposes here, the spark and glue context are only (currently) needed
# to get the logger.
spark_ctx = SparkSession.builder.getOrCreate()  # pyright: ignore
glue_ctx = GlueContext(spark_ctx)
logger = glue_ctx.get_logger()

# TODO:
#   - add error handling for the format of the document being incorrect
#   - figure out how we want to name and namespace clean files (e.g. will we
#     take the object key we're given, strip the extension and replace it with
#     one for the new format, or will we do something else)
#   - see what we can extract out of here to be useful for other ETLs. imagine
#     we'd have a few different things that could be made into a reusable
#     package

parameters = getResolvedOptions(
    sys.argv,
    [
        "RAW_BUCKET_NAME",
        "ALERT_OBJ_KEY",
        "CLEAN_BUCKET_NAME",
    ],
)

raw_bucket_name = parameters["RAW_BUCKET_NAME"]
alert_obj_key = parameters["ALERT_OBJ_KEY"]
clean_bucket_name = parameters["CLEAN_BUCKET_NAME"]

# NOTE: for now we'll take the alert object key and change out the file
#       extension for the clean data (leaving all namespacing and such). this
#       will probably need to change
clean_obj_key = alert_obj_key.replace(".docx", ".csv")

# NOTE: May need some creds here
s3_client = boto3.client("s3")

# try to get the docx object from S3 and handle any error that would keep us
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

# the response should contain a StreamingBody object that needs to be converted
# to a file like object to make the docx library happy
f = io.BytesIO(response.get("Body").read())
document = Document(f)

# NOTE: this document is assumed to contain a single table that needs to be
#       processed and nothing else. The file consists of:
#       - a 2 column header row that contains a column (0 index) with the alert
#         report date, which we need (rest of this row can be ignored)
#       - another header row that contains all the column names for the table
#       - rows of data
table = document.tables[0]
data = [[cell.text for cell in row.cells] for row in table.rows]
data = pd.DataFrame(data)

# grab the alert report date
date_received = pd.to_datetime(dparser.parse(data.iloc[0, 0], fuzzy=True))
# get the column list
data.columns = data.loc[1]
# drop the rows we no longer need (date and columns)
data.drop([0, 1], inplace=True)
data.reset_index(drop=True, inplace=True)

# now perform the ETL on the data rows
# NOTE: Questions about the data:
#           - Do we need to split this name to better enable queries later?
#           - will the name only ever be composed of first and last (i.e. no
#             middle name handling)?
#           - do we not want the lab id to carry over into clean data? same
#             with organism id (and anything else that doesn't carry over
#             currently). there's very little penalty (storage cost) for it
#             carrying over, and if it's not part of the AR log, we just don't
#             include it in the AR query, but we still have it if we end up
#             needing it for anything else
interim = pd.DataFrame()
interim["Mechanism (*Submitters Report)"] = data[
    "Anti-Microbial Resistance RT-PCR"
]
interim["Organism"] = data["Organism ID"]
interim["Date Received"] = date_received
interim["Date Reported"] = date_received
interim["Patient Name"] = data["Patient Name"]
interim["DOB"] = pd.to_datetime(data["DOB"], errors="coerce")
interim["Source"] = data["Source"].str.capitalize()
interim["Date of Collection"] = pd.to_datetime(
    data["Date of Collection"], errors="coerce"
)
interim["Testing Lab"] = "GPHL"
interim["Facility of Origin"] = data["Received from"]

# write out the transformed data
with io.StringIO() as csv_buff:
    interim.to_csv(csv_buff, index=False)

    response = s3_client.put_object(
        Bucket=clean_bucket_name, Key=clean_obj_key, Body=csv_buff.getvalue()
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
