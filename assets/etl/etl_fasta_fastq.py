import enum
import io
import json

import pyfastx
from capepy.aws.glue import EtlJob
from pyfastxcli import fastx_format_check

etl_job = EtlJob()
alert_obj_key = etl_job.parameters["ALERT_OBJ_KEY"]


class FastxTypes(enum.Enum):
    FASTA = "fasta"
    FASTQ = "fastq"


# TODO: maybe should live in `capepy` if it is generally useful in any way
def extract_objname_from_objkey():
    """Extract the object name from a full s3 object key.

    Returns:
        The name of the object without the leading namespacing info (e.g.
        objname.ext)
    """

    return alert_obj_key[alert_obj_key.rfind("/") + 1 :]


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


def handle_fasta(fname):
    """Handle a fasta file.

    Args:
        fname: The file/object name portion of the full key.

    Returns:
        A dict containing info for the fasta file that will be written to the
        "clean" json file.
    """
    fa = pyfastx.Fasta(fname)

    return {
        "raw_object": f"s3://{etl_job.parameters['RAW_BUCKET_NAME']}/{alert_obj_key}",
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


def handle_fastq(fname):
    """Handle a fastq file.

    Args:
        fname: The file/object name portion of the full key.

    Returns:
        A dict containing info for the fastq file that will be written to the
        "clean" json file.
    """
    fq = pyfastx.Fastq(fname)

    return {
        "raw_object": f"s3://{etl_job.parameters['RAW_BUCKET_NAME']}/{alert_obj_key}",
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


# and we need the object name itself (no leading namespacing info)
obj_name = extract_objname_from_objkey()

# the response should contain a StreamingBody object that needs to be converted
# to a file like object to make the docx library happy
f = io.BytesIO(etl_job.get_raw_file())

# we now have the file in memory, but need to write it locally because the
# pyfastx library only deals with file paths and not file-likes
with open(obj_name, "wb") as outfile:
    outfile.write(f.getbuffer())

try:
    frmt = fastx_format_check(obj_name)
    info = {}

    match frmt:
        case FastxTypes.FASTA.value:
            info = handle_fasta(obj_name)
        case FastxTypes.FASTQ.value:
            info = handle_fastq(obj_name)

except Exception as e:
    # NOTE: the library raises a generic Exception and so we catch
    #       nothing more specific
    etl_job.logger.error(f"Could not determine filetype for {obj_name}: {e}")
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
    etl_job.write_clean_file(buff.getvalue(), clean_obj_key)
