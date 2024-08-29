"""ETL script for raw Epi/HAI sequencing report pdf."""

import io
import sys
from datetime import datetime

import boto3 as boto3
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pypdf import PdfReader
from pyspark.sql import SparkSession
from tabula.io import read_pdf

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
clean_obj_key = alert_obj_key.replace(".pdf", ".csv")

# NOTE: May need some creds here
s3_client = boto3.client("s3")

# try to get the pdf object from S3 and handle any error that would keep us
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
# to a file like object to make the pdf libraries happy
f = io.BytesIO(response.get("Body").read())

try:
    # get the report date from the 4th line of the pdf
    reader = PdfReader(f)
    page = reader.pages[0]
    date_reported = page.extract_text().split("\n")[3].strip()
    datetime.strptime(date_reported,'%m/%d/%Y')
except ValueError as err:
    err_message = (
            f"ERROR - Could not properly read sequencing report date. "
            f"ETL will continue."
            f"{err}"
        )

    logger.error(err_message)

    date_reported = ""

try:
    # get two tables from the pdf
    tables = read_pdf(f, multiple_tables=True, pages=2)
    mlst_st = tables[0]
    genes = tables[1]
except (IndexError, KeyError) as err:
    err_message = (
            f"ERROR - Could not properly read sequencing PDF tables. "
            f"ETL Cannot continue."
            f"{err}"
        )

    logger.error(err_message)

    # NOTE: need to properly handle exception stuff here, and we probably
    #       want this going somewhere very visible (e.g. SNS topic or a
    #       perpetual log as someone will need to be made aware)
    raise Exception(err_message)

# filter the columns we need and join the tables together
interim = mlst_st[["Accession_ID", "WGS_ID", "MLST_ST"]]
genes_inter = genes.set_index("Unnamed: 0").T
genes_interim = genes_inter.filter(regex="(NDM|KPC|IMP|OXA|VIM|CMY)", axis=1)
interim = interim.join(genes_interim, on="WGS_ID")
interim["Date Reported"] = date_reported

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
