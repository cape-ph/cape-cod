import csv
import datetime
import gzip
import io
import json
import tarfile

from capepy.aws.glue import EtlJob

etl_job = EtlJob()

# This ETL expects to operate on a tar.gz file containing a metadata file
# (meta.json) and a `sequencing` directory containing some number of gzipped
# files fastx files (fasta, fastq). The metadata will be extracted, augmented
# for later use and then written to the clean data sink. The fastx files will be
# contcatenated into a single gzipped fastx and also written to the clean data
# sink. Each individual sequencing file is additionally written out on its own
# (gzipped) under the `sequencing-reads-split` prefix in the clean data sink.
# The prefix for the clean data will be constructed from the sample_id
# (from the meta) and the current UTC date/time

archive_obj_key = etl_job.parameters["OBJECT_KEY"]

sample_archive = etl_job.get_src_file()
archbio = io.BytesIO(sample_archive)

# basic tar file check
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
    f"sample_id={sample_id}/year={processed_dt.year}/month={processed_dt.month}/"
    f"day={processed_dt.day}/hour={processed_dt.hour}/"
    f"minute={processed_dt.minute}/second={processed_dt.second}"
)

reads_key = "/".join(["sequencing-reads", sink_prefix, "sequencing-reads.gz"])

# collect (key, size) for each individual split read file as it is written so
# a per-upload manifest of the full set can be emitted below.
split_files = []

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
        # we are not really doing much validation here. if a filename ends in
        # fasta/fastq we'll gzip it inplace and the add it to the concat file.
        # otherwise we'll assume it's already a gzipped file and move on.
        # TODO: this could be a bit more robust and specifically check other
        #       files for being valid gzips and stuff like that. when we get out
        #       of this being for a demo, we will need to rearchitect this a bit
        #       anyway and should address better handling at that time
        with tf.extractfile(mn) as br:
            bytes_for_concat = None
            if mn.endswith(("fasta", "fastq")):
                etl_job.logger.info(
                    "input archive member is not gzipped. gzipping."
                )
                bytes_for_concat = gzip.compress(br.read())
            else:
                bytes_for_concat = br.read()
            gzbuff.write(bytes_for_concat)

            # also write this member out on its own (un-concatenated) under a
            # dedicated prefix so the per-read files are available in the clean
            # sink. keep one consistent gzip format: fasta/fastq members were
            # gzipped above, already-gzipped members pass through as-is.
            member_name = mn.rsplit("/", 1)[-1]
            if mn.endswith(("fasta", "fastq")):
                split_name = f"{member_name}.gz"
            else:
                split_name = member_name
            split_key = "/".join(
                ["sequencing-reads-split", sink_prefix, split_name]
            )
            with io.BytesIO(bytes_for_concat) as splitbuff:
                splitbuff.seek(0)
                etl_job.write_sink_file(splitbuff, split_key)

            split_files.append(
                {"key": split_key, "size": len(bytes_for_concat)}
            )

    # write out the new clean uber sequencing file
    gzbuff.seek(0)
    etl_job.write_sink_file(
        gzbuff,
        reads_key,
    )

# write a manifest of the individual split read files for this upload as CSV
# under a dedicated `manifest` prefix (one row per split file), keyed by the
# same sink prefix as the rest of the upload's outputs. this is crawled into
# the data catalog like meta.csv, so the set of files extracted from a single
# uploaded archive is queryable (e.g. by sample_id or source archive). the
# notify queue also emits a notification for this object (see the
# `split-reads-manifest` rule in the stack config), so consumers of the
# individual reads can learn the full set from an upload.
manifest_fields = [
    "sample_id",
    "source_archive_key",
    "sink_prefix",
    "file_key",
    "file_size",
]
manifest_buf = io.StringIO()
manifest_writer = csv.DictWriter(manifest_buf, fieldnames=manifest_fields)
manifest_writer.writeheader()
for split_file in split_files:
    manifest_writer.writerow(
        {
            "sample_id": sample_id,
            "source_archive_key": archive_obj_key,
            "sink_prefix": sink_prefix,
            "file_key": split_file["key"],
            "file_size": split_file["size"],
        }
    )
manifest_key = "/".join(["manifest", sink_prefix, "manifest.csv"])
with io.BytesIO(manifest_buf.getvalue().encode("utf-8")) as manifestbuff:
    manifestbuff.seek(0)
    etl_job.write_sink_file(manifestbuff, manifest_key)

# add the s3 path to the concatenated sequencing file into meta
concat_gz_s3loc = "/".join(
    [
        f"s3://{etl_job.parameters['SINK_BUCKET_NAME']}",
        reads_key,
    ]
)
meta["sequencing_reads"] = concat_gz_s3loc

# meta comes with camel case, cause javascript. get it into snake case since
# that's what we use everywhere but front ends...
# python 3.7+ specific, we rely on dict order being insertion order for this to
# work as is.
key_map = {
    "sampleType": "sample_type",
    "sampleMatrix": "sample_matrix",
    "sampleCollectionLocation": "sample_collection_location",
    "sampleCollectionDate": "sample_collection_date",
    # this column name is already normalized since we added it in this etl
    "sequencing_reads": "sequencing_reads",
    # NOTE: if more fields are added to meta.json, this needs to be updated or they
    #       will never be seen in the csv file. All new fields should be added to
    #       the end of this dict so as to not mess up already catalogged data
}

# since this is a small dict we'll just make a new one instead of modifying in
# place
normalized_meta = {v: meta[k] for k, v in key_map.items()}

# convert json to csv for queryability
strbuf = io.StringIO()
writer = csv.DictWriter(strbuf, fieldnames=key_map.values())
writer.writeheader()
writer.writerow(normalized_meta)

# then write normalized_meta into clean as well
with io.BytesIO(strbuf.getvalue().encode("utf-8")) as metabuff:
    metabuff.seek(0)
    etl_job.write_sink_file(
        metabuff, "/".join(["meta", sink_prefix, "meta.csv"])
    )

# TODO: delete raw file?
