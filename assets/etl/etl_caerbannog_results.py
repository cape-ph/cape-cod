"""ETL for the caerbannog consumer result archive.

The consumer writes one `.tar.gz` per run (one run == one user upload) to the
seqauto `result-raw` bucket under the `caerbannog-output` prefix. This job
unpacks it and writes CSV to `result-clean`, where the existing crawler catalogs
the outputs as `result_caerbannog_*` tables alongside the bactopia tables.

Archive contents:

    archive.tar.gz/
      |- aggregate.csv                 (pre-aggregated; near passthrough)
      |- <prefix>-stoplight.json         (per-sample/batch)
      |- <prefix>-cluster-estimates.json (per-sample/batch)

The stoplight and cluster-estimates JSON are each a single nested object: a
sample-level summary carrying `sample_id` plus an array of per-record entries
(target detections / cluster summaries). Each is flattened to one CSV row per
array entry, with the sample- and document-level fields denormalized onto every
row and `sample_id` (the report join key) read from inside the document.

TODO(#363): the archive packaging (single .tar.gz, the aggregate CSV filename,
directory layout) is the consumer->datalake delivery contract and is still
provisional; the per-file parsing below matches the confirmed output formats.
CSV output (not columnar) is intentional; the columnar move is #364.
"""

import csv
import io
import json
import os
import re
import tarfile

from capepy.aws.glue import EtlJob

etl_job = EtlJob()

# archive member classification (by basename). the aggregate CSV filename is
# provisional (TODO(#363)); the JSON suffixes match the confirmed output naming.
AGGREGATE_OBJ = "aggregate.csv"
STOPLIGHT_SUFFIX = "stoplight.json"
CLUSTER_SUFFIX = "cluster-estimates.json"

# top-level output folders under the clean sink. the result-clean crawler walks
# the whole bucket and names each top-level folder `result_<name>` (e.g. the
# bactopia data function queries `result_amrfinderplus`), so these are
# namespaced under `caerbannog_` to avoid colliding with the bactopia tables.
AGGREGATE_TABLE = "caerbannog_aggregate"
STOPLIGHT_TABLE = "caerbannog_stoplight"
CLUSTER_TABLE = "caerbannog_cluster_estimates"

# per-run partition column (one archive == one run), mirroring bactopia_run.
RUN_PARTITION = "caerbannog_run"

# explicit, stable CSV headers so every run partition writes the same columns
# in the same order (the crawler infers types per column across partitions).
STOPLIGHT_COLUMNS = [
    "sample_id",
    "rule_set_version",
    "software_version",
    "status",
    "error_message",
    "datetime",
    "num_reads",
    "category",
    "category_threat_severity",
    "category_assessment",
    "category_confidence",
    "target_name",
    "target_description",
    "target_severity",
    "target_assessment",
    "target_confidence",
]

CLUSTER_COLUMNS = [
    "sample_id",
    "rule_set_version",
    "software_version",
    "status",
    "error_message",
    "num_reads",
    "num_batches",
    "match_cluster_id",
    "num_matches",
    "target_name",
    "target_description",
    "target_severity",
    "estimated_likelihood",
    "estimated_fraction",
]


def normalize_stoplight(record):
    """Flatten a stoplight document to one row per target detection.

    The document is a single object with a `sample_threat_assessment` summary
    (sample_id, num_reads, category_assessments[]); each category carries its
    own assessment and a list of target detections. Sample- and category-level
    fields are denormalized onto every target row. A category with no detections
    still yields one row (blank target fields), and a document with no
    categories still yields one sample-level row, so the sample always appears.
    """
    summary = record.get("sample_threat_assessment") or {}
    base = {
        "sample_id": summary.get("sample_id", ""),
        "rule_set_version": record.get("rule_set_version", ""),
        "software_version": record.get("software_version", ""),
        "status": record.get("status", ""),
        "error_message": record.get("error_message", ""),
        "datetime": record.get("datetime", ""),
        "num_reads": summary.get("num_reads", ""),
    }

    rows = []
    for category in summary.get("category_assessments") or []:
        cat_base = {
            **base,
            "category": category.get("category", ""),
            "category_threat_severity": category.get("threat_severity", ""),
            "category_assessment": category.get("category_assessment", ""),
            "category_confidence": category.get("confidence", ""),
        }
        detections = category.get("target_detections") or []
        if not detections:
            rows.append(cat_base)
        for detection in detections:
            rows.append(
                {
                    **cat_base,
                    "target_name": detection.get("target_name", ""),
                    "target_description": detection.get(
                        "target_description", ""
                    ),
                    "target_severity": detection.get("target_severity", ""),
                    "target_assessment": detection.get("target_assessment", ""),
                    "target_confidence": detection.get("confidence", ""),
                }
            )

    return rows or [base]


def normalize_cluster_estimates(record):
    """Flatten a cluster-estimates document to one row per cluster summary.

    The document is a single object with a `sample_target_summary` (sample_id,
    num_reads, num_batches, cluster_summaries[]). Sample- and document-level
    fields are denormalized onto every cluster row. A document with no cluster
    summaries still yields one sample-level row so the sample always appears.
    """
    summary = record.get("sample_target_summary") or {}
    base = {
        "sample_id": summary.get("sample_id", ""),
        "rule_set_version": record.get("rule_set_version", ""),
        "software_version": record.get("software_version", ""),
        "status": record.get("status", ""),
        "error_message": record.get("error_message", ""),
        "num_reads": summary.get("num_reads", ""),
        "num_batches": summary.get("num_batches", ""),
    }

    rows = []
    for cluster in summary.get("cluster_summaries") or []:
        rows.append(
            {
                **base,
                "match_cluster_id": cluster.get("match_cluster_id", ""),
                "num_matches": cluster.get("num_matches", ""),
                "target_name": cluster.get("target_name", ""),
                "target_description": cluster.get("target_description", ""),
                "target_severity": cluster.get("target_severity", ""),
                "estimated_likelihood": cluster.get("estimated_likelihood", ""),
                "estimated_fraction": cluster.get("estimated_fraction", ""),
            }
        )

    return rows or [base]


def _rows_to_csv(rows, fieldnames):
    """Serialize dict rows to a CSV string with a fixed header.

    Missing keys are written as empty cells and unexpected keys are dropped, so
    every partition emits exactly `fieldnames` in order.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=fieldnames, restval="", extrasaction="ignore"
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _json_outputs_to_rows(members, normalizer):
    """Parse and normalize matched JSON members to flat rows.

    Args:
        members: List of (member_name, raw_bytes) tuples.
        normalizer: The per-type normalization function.

    Returns:
        The concatenated rows from every member.
    """
    rows = []
    for member_name, raw in members:
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
        rows.extend(normalizer(record))
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

    if basename == AGGREGATE_OBJ:
        with tf.extractfile(member_name) as br:
            aggregate_bytes = br.read()
        continue

    if basename.endswith(CLUSTER_SUFFIX):
        with tf.extractfile(member_name) as br:
            cluster_members.append((member_name, br.read()))
        continue

    if basename.endswith(STOPLIGHT_SUFFIX):
        with tf.extractfile(member_name) as br:
            stoplight_members.append((member_name, br.read()))
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
        stoplight_members, normalize_stoplight
    )
    stoplight_key = os.path.join(
        STOPLIGHT_TABLE, f"{RUN_PARTITION}={run_id}", "stoplight.csv"
    )
    print(f"Writing stoplight output to {stoplight_key}")
    etl_job.write_sink_file(
        _rows_to_csv(stoplight_rows, STOPLIGHT_COLUMNS), stoplight_key
    )

if cluster_members:
    cluster_rows = _json_outputs_to_rows(
        cluster_members, normalize_cluster_estimates
    )
    cluster_key = os.path.join(
        CLUSTER_TABLE, f"{RUN_PARTITION}={run_id}", "cluster_estimates.csv"
    )
    print(f"Writing cluster-estimates output to {cluster_key}")
    etl_job.write_sink_file(
        _rows_to_csv(cluster_rows, CLUSTER_COLUMNS), cluster_key
    )
