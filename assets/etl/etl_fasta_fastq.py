import enum
import io
import json
import sys

import boto3 as boto3
import pyfastx
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyfastxcli import fastx_format_check
from pyspark.sql import SparkSession


class FastxTypes(enum.Enum):
    FASTA = "fasta"
    FASTQ = "fastq"


def extract_objname_from_objkey(objkey):
    """Extract the object name from a full s3 object key.

    Args:
        objkey: The full s3 key for an object (e.g. /subdir/objname.ext)

    Returns:
        The name of the object without the leading namespacing info (e.g.
        objname.ext)
    """

    return objkey[objkey.rfind("/") + 1 :]


# TODO:
# * GET ME MOVED TO MY OWN REPO
# * fasta and fastq handling are very similar. these 2 functions could be
#   cleaned up quite a bit to remove similarities if desired. for now these are
#   being left as 2 fcuntions in case we need to change how we're handling the
#   files as things become clearer.
# * the handle_ functions each take the file name and full originating key. this
#   isn't really needed as we have a function above to extract the filename from
#   the key. but the filename had already been extracted in the caller and
#   passing it was chosen. if/when we clean up fastx handling, re-examine


def handle_fasta(objkey, fname, raw_bucket):
    """Handle a fasta file.

    Args:
        objkey: The full object key for the original file.
        fname: The file/object name portion of the full key.
        raw_bucket: the name of the raw_bucket the original object lives in.

    Returns:
        A dict containing info for the fasta file that will be writtent to the
        "clean" json file.
    """
    fa = pyfastx.Fasta(fname)

    return {
        "raw_object": f"s3://{raw_bucket}/{objkey}",
        "file_name": fname,
        "format": FastxTypes.FASTA.value,
        "fasta_type": fa.type,
        "num_sequences": len(fa),
        "total_sequence_len": fa.size,
        "gc_content": fa.gc_content,
        "gc_skews": fa.gc_skew,
        "composition": fa.composition,
        "is_gzip": fa.is_gzip,
    }


def handle_fastq(objkey, fname, raw_bucket):
    """Handle a fastq file.

    Args:
        objkey: The full object key for the original file.
        fname: The file/object name portion of the full key.
        raw_bucket: the name of the raw_bucket the original object lives in.

    Returns:
        A dict containing info for the fastq file that will be writtent to the
        "clean" json file.
    """
    fq = pyfastx.Fastq(fname)

    return {
        "raw_object": f"s3://{raw_bucket}/{objkey}",
        "file_name": fname,
        "format": FastxTypes.FASTQ.value,
        "num_sequences": len(fq),
        "total_sequence_len": fq.size,
        "gc_content": fq.gc_content,
        "composition": fq.composition,
        "is_gzip": fq.is_gzip,
        "avg_read_len": fq.avglen,
        "max_read_len": fq.maxlen,
        "min_read_len": fq.minlen,
        "min_quality_score": fq.minqual,
        "max_quality_score": fq.maxqual,
        "fastq_phred": fq.phred,
        "guessed_encoding_type": fq.encoding_type,
    }


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

raw_bucket_name = parameters["RAW_BUCKET_NAME"]
alert_obj_key = parameters["ALERT_OBJ_KEY"]
clean_bucket_name = parameters["CLEAN_BUCKET_NAME"]


# and we need the object name itself (no leading namespacing info)
obj_name = extract_objname_from_objkey(alert_obj_key)

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

# handle the file itself...

# the response should contain a StreamingBody object that needs to be converted
# to a file like object to make the docx library happy
f = io.BytesIO(response.get("Body").read())

# we now have the file in memory, but need to write it locally because the
# pyfastx library only deals with file paths and not file-likes
with open(obj_name, "wb") as outfile:
    outfile.write(f.getbuffer())

try:
    frmt = fastx_format_check(obj_name)
    info = {}

    match frmt:
        case FastxTypes.FASTA.value:
            info = handle_fasta(alert_obj_key, obj_name, raw_bucket_name)
        case FastxTypes.FASTQ.value:
            info = handle_fastq(alert_obj_key, obj_name, raw_bucket_name)

except Exception as e:
    # NOTE: the library raises a generic Exception and so we catch
    #       nothing more specific
    logger.error(f"Could not determine filetype for {obj_name}: {e}")
    raise e


# NOTE: for now we'll take the alert object key and change out the file
#       extension for the clean data (leaving all namespacing and such) and add
#       the format (fasta/fastq). this will probably need to change.
# NOTE: these may be a number of different extension formats, so we're just
#       chopping off at the first '.'
clean_obj_key = f"{alert_obj_key[0:alert_obj_key.find('.')]}.{frmt}.json"


# write out our "clean" data
with io.StringIO() as buff:
    json.dump(info, buff)

    response = s3_client.put_object(
        Bucket=clean_bucket_name, Key=clean_obj_key, Body=buff.getvalue()
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
