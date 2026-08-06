"""ETL for the caerbannog consumer result archive.

The consumer writes one `.tar.gz` per run (one run == one user upload) to the
seqauto `result-raw` bucket under the `caerbannog-output` prefix. This job
unpacks it and writes CSV to `result-clean`, where the existing crawler catalogs
the outputs as `result_caerbannog_*` tables alongside the bactopia tables.

Archive layout:

    archive.tar.gz/
      |- aggregate.csv                 (pre-aggregated; near passthrough)
      |- individual-outputs/
         |- stoplight-<n>.json         (per-sample)
         |- cluster-estimates-<n>.json (per-sample)

TODO(#363): archive member names and the JSON record schemas are provisional
until the consumer contract is finalized. The format-dependent seams are
derive_sample_id, normalize_stoplight, and normalize_cluster_estimates. CSV
output (not columnar) is intentional; the datalake-wide columnar move is #364.
"""

import csv
import io
import json
import os
import re
import tarfile

from capepy.aws.glue import EtlJob

etl_job = EtlJob()

# archive members of interest. TODO(#363): names provisional.
INDIVIDUAL_DIR = "individual-outputs/"
AGGREGATE_OBJ = "aggregate.csv"
STOPLIGHT_STEM = "stoplight"
CLUSTER_STEM = "cluster-estimates"

# top-level output folders under the clean sink. the result-clean crawler walks
# the whole bucket and names each top-level folder `result_<name>` (e.g. the
# bactopia data function queries `result_amrfinderplus`), so these are
# namespaced under `caerbannog_` to avoid colliding with the bactopia tables.
AGGREGATE_TABLE = "caerbannog_aggregate"
STOPLIGHT_TABLE = "caerbannog_stoplight"
CLUSTER_TABLE = "caerbannog_cluster_estimates"

# per-run partition column (one archive == one run), mirroring bactopia_run.
RUN_PARTITION = "caerbannog_run"

# sample id column injected into every individual-output row (report join key).
SAMPLE_ID_COL = "sample_id"


def derive_sample_id(member_basename, stem):
    """Derive the sample name (report join key) for an individual output file.

    TODO(#363): the consumer encodes the sample in the filename today, but a
    sidecar metadata file is also on the table. This strips the known stem and
    the `.json` suffix; replace once the contract is fixed.

    Args:
        member_basename: The archive member file name without its directory.
        stem: The known filename stem for this output type (e.g. `stoplight`).

    Returns:
        The derived sample id as a string.
    """
    name = member_basename
    if name.endswith(".json"):
        name = name[: -len(".json")]
    name = re.sub(rf"^{re.escape(stem)}[-_]?", "", name)
    return name or member_basename


def _scalarize(value):
    """Flatten a JSON value to a CSV-safe cell, json-encoding nested values."""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def _normalize_records(record):
    """Flatten a parsed JSON document (object or list) to flat rows.

    TODO(#363): schema-agnostic placeholder - flattens one level and
    json-encodes nested values until the real schema lands.
    """
    items = record if isinstance(record, list) else [record]
    rows = []
    for item in items:
        if isinstance(item, dict):
            rows.append({k: _scalarize(v) for k, v in item.items()})
        else:
            rows.append({"value": _scalarize(item)})
    return rows


def normalize_stoplight(record):
    """Normalize a stoplight JSON document to flat CSV rows.

    Distinct seam from cluster-estimates so each type can get its own column
    mapping in the #363 second pass without disturbing the other.
    """
    return _normalize_records(record)


def normalize_cluster_estimates(record):
    """Normalize a cluster-estimates JSON document to flat CSV rows."""
    return _normalize_records(record)


def _rows_to_csv(rows):
    """Serialize dict rows to a CSV string with a stable header.

    The header is the union of keys across all rows in first-seen order, so a
    ragged record set still yields one well-formed table. `sample_id` is
    inserted first per row, so it leads the header.
    """
    fieldnames = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=fieldnames, restval="", extrasaction="ignore"
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _json_outputs_to_rows(members, stem, normalizer):
    """Convert matched individual-output JSON members to sample-tagged rows.

    Args:
        members: List of (member_name, raw_bytes) tuples.
        stem: The filename stem for this output type (for sample id derivation).
        normalizer: The per-type normalization function.

    Returns:
        A list of flat dict rows, each carrying a leading `sample_id` column.
    """
    rows = []
    for member_name, raw in members:
        basename = member_name.rsplit("/", 1)[-1]
        sample_id = derive_sample_id(basename, stem)
        try:
            record = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as err:
            # name the malformed member, then re-raise so the job fails visibly
            msg = (
                f"Caerbannog result member {member_name} is not valid JSON: "
                f"{err}"
            )
            etl_job.logger.error(msg)
            raise ValueError(msg) from err
        for flat in normalizer(record):
            rows.append({SAMPLE_ID_COL: sample_id, **flat})
    return rows


archive_obj_key = etl_job.parameters["OBJECT_KEY"]

# per-run partition value derived from the archive object name.
archive_basename = archive_obj_key.rsplit("/", 1)[-1]
run_id = re.sub(r"\.tar\.gz$|\.tgz$|\.tar$|\.gz$", "", archive_basename)
run_id = re.sub(r"[^A-Za-z0-9._-]", "_", run_id) or "unknown_run"

sample_archive = etl_job.get_src_file()
archbio = io.BytesIO(sample_archive)

if not tarfile.is_tarfile(archbio):
    msg = (
        f"The given caerbannog result archive {archive_obj_key} is malformed "
        f"and cannot be opened."
    )
    etl_job.logger.error(msg)
    raise tarfile.ReadError(msg)

archbio.seek(0)

# streaming body opens with mode "r" (transparent), not "r:gz", even for a
# tar.gz. See etl_seqarchive.py for the rationale.
tf = tarfile.open(fileobj=archbio, mode="r")

# TODO(#363): hardening deferred (shared with etl_seqarchive.py) - tar traversal
# safety, large-archive memory footprint, malformed-input feedback to uploader.

aggregate_bytes = None
stoplight_members = []
cluster_members = []

for member_name in tf.getnames():
    basename = member_name.rsplit("/", 1)[-1]
    if not basename:
        continue

    if member_name == AGGREGATE_OBJ:
        with tf.extractfile(member_name) as br:
            aggregate_bytes = br.read()
        continue

    if member_name.startswith(INDIVIDUAL_DIR) and basename.endswith(".json"):
        if basename.startswith(STOPLIGHT_STEM):
            with tf.extractfile(member_name) as br:
                stoplight_members.append((member_name, br.read()))
        elif basename.startswith(CLUSTER_STEM):
            with tf.extractfile(member_name) as br:
                cluster_members.append((member_name, br.read()))
        else:
            etl_job.logger.info(
                f"Ignoring unrecognized individual output {member_name}."
            )
        continue

    etl_job.logger.info(f"Ignoring unrecognized archive member {member_name}.")

if not any([aggregate_bytes, stoplight_members, cluster_members]):
    print(
        f"Caerbannog result ETL found no recognized content in "
        f"{archive_obj_key}. Nothing to process."
    )
    # TODO(#363): job shows as failed in the console; should be a success
    # (shared with the bactopia ETL).
    os._exit(0)

# aggregate CSV: near passthrough (already crawler friendly)
if aggregate_bytes is not None:
    aggregate_key = os.path.join(
        AGGREGATE_TABLE, f"{RUN_PARTITION}={run_id}", "aggregate.csv"
    )
    print(f"Writing aggregate output to {aggregate_key}")
    with io.BytesIO(aggregate_bytes) as aggbuff:
        aggbuff.seek(0)
        etl_job.write_sink_file(aggbuff, aggregate_key)

if stoplight_members:
    stoplight_rows = _json_outputs_to_rows(
        stoplight_members, STOPLIGHT_STEM, normalize_stoplight
    )
    stoplight_key = os.path.join(
        STOPLIGHT_TABLE, f"{RUN_PARTITION}={run_id}", "stoplight.csv"
    )
    print(f"Writing stoplight output to {stoplight_key}")
    etl_job.write_sink_file(_rows_to_csv(stoplight_rows), stoplight_key)

if cluster_members:
    cluster_rows = _json_outputs_to_rows(
        cluster_members, CLUSTER_STEM, normalize_cluster_estimates
    )
    cluster_key = os.path.join(
        CLUSTER_TABLE, f"{RUN_PARTITION}={run_id}", "cluster_estimates.csv"
    )
    print(f"Writing cluster-estimates output to {cluster_key}")
    etl_job.write_sink_file(_rows_to_csv(cluster_rows), cluster_key)
