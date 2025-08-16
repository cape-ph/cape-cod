import datetime
import io
import json
import tarfile

from capepy.aws.glue import EtlJob

etl_job = EtlJob()

# This ETL expects to operate on a tar.gz file containing a metatdata file
# (meta.json) and a `sequencing` directory containing some number of gzipped
# files fastx files (fasta, fastq). The metadata will be extracted, augmented
# for later use and then written to the clean data sink. The fastx files will be
# contcatenated into a single gzipped fastx and also written to the clean data
# sink. The prefix for the clean data will be constructed from the sample_id
# (from the meta) and the current UTC date/time

archive_obj_key = etl_job.parameters["OBJECT_KEY"]

sample_archive = etl_job.get_src_file()
archbio = io.BytesIO(sample_archive)

# baisc tar file check
if not tarfile.is_tarfile(archbio):
    msg = (
        f"The given sample reads archive {archive_obj_key} is malformed and "
        f"cannot be opened."
    )

    etl_job.logger.error(msg)
    raise tarfile.ReadError(msg)

archbio.seek(0)

# TODO: not handling errors in format really, which is probably ok as the
#       exception will get logged in cloudwatch, but the bigger deal is that we
#       cannot inform the user that the archive was mal-formed at this point.

# NOTE: when processing the streaming body here, the open mode for the tarfile
#       is "r" *not* "r:gz" (even though we're streaming a tar.gz. If you were
#       to download the file and write to disk, you would need to go back to
#       "r:gz"

# open as TarFile and get the meta out
tf = tarfile.open(fileobj=archbio, mode="r")
meta = json.load(tf.extractfile("meta.json"))

# grab things we need for later naming
sample_id = meta["sampleId"]
processed_dt = datetime.datetime.now(datetime.timezone.utc)

# construct the prefix for all files written here
sink_prefix = (
    f"{sample_id}/year={processed_dt.year}/month={processed_dt.month}/"
    f"day={processed_dt.day}/hour={processed_dt.hour}/"
    f"minute={processed_dt.minute}/second={processed_dt.second}"
)

# start with the gzip files
with io.BytesIO() as gzbuff:
    # TODO:
    #   - make sure no possible tar traversal vulns (don't think so since we
    #     limit to a specific prefix that can't be `/` or `..`)
    #   - memory requirements for this lambda may be large given we could get
    #     enormous archives (possible remediation in attaching filesystem for
    #     the lambda?)
    #   - direct read->write of the members seems scary

    # concat all files in `sequncing` dir
    for mn in sorted(
        [mn for mn in tf.getnames() if mn.startswith("sequencing/")]
    ):
        with tf.extractfile(mn) as br:
            gzbuff.write(br.read())

    # write out the new clean uber sequencing file
    gzbuff.seek(0)
    etl_job.write_sink_file(
        gzbuff, "/".join([sink_prefix, "sequencing-reads.gz"])
    )

# add the s3 path to the concatenated sequencing file into meta
concat_gz_s3loc = "/".join(
    [
        f"s3://{etl_job.parameters['SRC_BUCKET_NAME']}/",
        sink_prefix,
        "sequencing-reads.gz",
    ]
)
meta["sequencing_reads"] = concat_gz_s3loc

# the write meta into clean as well
with io.BytesIO(json.dumps(meta).encode("utf-8")) as metabuff:
    metabuff.seek(0)
    etl_job.write_sink_file(metabuff, "/".join([sink_prefix, "meta.json"]))

# TODO: delete raw file?
