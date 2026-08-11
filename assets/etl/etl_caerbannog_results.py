"""ETL for the caerbannog consumer result archive.

The consumer writes one `<sample_id>.tar.gz` per run (one run == one user
upload) to the seqauto `result-raw` bucket under the `caerbannog-output` prefix,
keyed by the verbatim input-clean sink prefix:

    caerbannog-output/sample_id=<id>/year=<y>/month=<m>/day=<d>/hour=<h>/
        minute=<min>/second=<s>/<sample_id>.tar.gz

This job unpacks it and writes CSV to `result-clean` under that same sink
prefix, so the crawler catalogs `result_caerbannog_*` tables partitioned by
sample_id/year/.../second - matching the input-clean tables so Athena can join
across the lake on the sample_id partition.

Archive contents:

    <sample_id>.tar.gz/
      |- result_meta.json                    (delivery metadata)
      |- <sample_id>-stoplight.json          (single, latest batch)
      |- <sample_id>-cluster-estimates.json  (single, latest batch)

`result_meta.json` names the stoplight/cluster members (`stoplight`,
`cluster_estimates`); this job reads those keys to locate them. There is
exactly one stoplight and one cluster file per archive. The transformed
stoplight rows carry everything the report needs.

The stoplight and cluster-estimates JSON are each a single nested object: a
sample-level summary plus an array of per-record entries (target detections /
cluster summaries). Each is flattened to one CSV row per array entry, with the
sample- and document-level fields denormalized onto every row. `sample_id` is
NOT written as a data column - it is the partition, supplied by the object key
(the input-clean `meta` table works the same way).

TODO(#363): this job also renders a TEMPORARY self-contained HTML report from
the stoplight rows (see render_report_html). Report rendering does not belong in
the ETL; it is a stopgap for the demo and moves out to a dedicated reporting
path in a later branch, at which point the jinja2 dependency and this code are
removed. CSV output (not columnar) is intentional; the columnar move is #364.
"""

import csv
import io
import json
import tarfile

from capepy.aws.glue import EtlJob
from jinja2 import Template

etl_job = EtlJob()

# archive member names come from result_meta.json (see module docstring); the
# consumer names them <sample_id>-stoplight.json / <sample_id>-cluster-estimates.json.
META_OBJ = "result_meta.json"

# result-raw object keys are `<ROOT_PREFIX>/<sink_prefix>/<sample_id>.tar.gz`,
# where <sink_prefix> is the verbatim input-clean partition prefix written by
# etl_seqarchive.py. we recover it from the object key and reuse it verbatim for
# the result-clean outputs so their partitions line up with input-clean.
ROOT_PREFIX = "caerbannog-output"

# top-level output folders under the clean sink. the result-clean crawler walks
# the whole bucket and names each top-level folder `result_<name>` (e.g. the
# bactopia data function queries `result_amrfinderplus`), so these are
# namespaced under `caerbannog_` to avoid colliding with the bactopia tables.
STOPLIGHT_TABLE = "caerbannog_stoplight"
CLUSTER_TABLE = "caerbannog_cluster_estimates"

# TEMPORARY: the self-contained HTML report is written under this prefix, which
# the result-clean crawler EXCLUDES (Pulumi.cape-cod-dev.yaml) so it is not
# cataloged as a table. See render_report_html's TODO(#363).
REPORT_PREFIX = "caerbannog-report"

# explicit, stable CSV headers so every run partition writes the same columns
# in the same order (the crawler infers types per column across partitions).
STOPLIGHT_COLUMNS = [
    "rule_set_version",
    "software_version",
    "status",
    "error_message",
    "datetime",
    "num_reads",
    "category",
    "category_severity",
    "category_assessment",
    "category_confidence",
    "target_name",
    "target_description",
    "target_severity",
    "target_assessment",
    "target_confidence",
]

CLUSTER_COLUMNS = [
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
            "category_severity": category.get("threat_severity", ""),
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


def parse_sink_prefix(object_key, root_prefix):
    """Recover the input-clean sink prefix from a result-raw object key.

    Result-raw keys are `<root_prefix>/<sink_prefix>/<archive>`, where
    <sink_prefix> is the verbatim `sample_id=.../year=.../.../second=...` prefix
    written by etl_seqarchive.py. This strips the leading `<root_prefix>/` and
    the trailing `/<archive>` and returns the middle. Reusing it verbatim keeps
    the result-clean partitions aligned with input-clean.

    A key that does not carry a `sample_id=` partition is a contract violation;
    we log loudly and fall back to `sample_id=unknown` so the run still lands
    somewhere inspectable rather than crashing.
    """
    key = object_key
    prefix = f"{root_prefix}/"
    if key.startswith(prefix):
        key = key[len(prefix) :]
    sink_prefix, _, _archive = key.rpartition("/")
    if not sink_prefix.startswith("sample_id="):
        etl_job.logger.error(
            f"Caerbannog result key {object_key} does not carry the expected "
            f"'sample_id=' sink prefix under {root_prefix}/; result-clean "
            f"partitions will NOT align with input-clean. Falling back to "
            f"'sample_id=unknown'."
        )
        return "sample_id=unknown"
    return sink_prefix


# report row columns, in the template's header order (Threat, Severity, Threat
# Assessment, Confidence, Description). the template renders row.items() in
# order, so the projection below must build each row with exactly these keys.
REPORT_ROW_FIELDS = (
    "target_name",
    "target_severity",
    "target_assessment",
    "target_confidence",
    "target_description",
)


def stoplight_report_rows(stoplight_rows):
    """Project normalized stoplight rows to the report's per-target rows.

    Keeps only rows with a non-blank target_name, ordering each to exactly the
    template header columns. Splits on target_assessment == "clear" into
    (active, cleared), mirroring the report data function's split.
    """
    active = []
    cleared = []
    for row in stoplight_rows:
        if not row.get("target_name"):
            continue
        projected = {field: row.get(field, "") for field in REPORT_ROW_FIELDS}
        if projected["target_assessment"] == "clear":
            cleared.append(projected)
        else:
            active.append(projected)
    return active, cleared


# TEMPORARY (TODO(#363)) self-contained HTML report template. The two table
# blocks are duplicated from the bactopia report template
# (assets/report/bactopia-single-sample-analysis/template.html.j2, commit
# 3251ccd); the surrounding <html>/<head>/<style> make it standalone. This
# lives here only for the demo - see render_report_html.
REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>RABiTS Sample Results - {{ sample_id }}</title>
    <style>
      body {
        margin: 0;
        padding: 24px;
        max-width: 980px;
        margin-inline: auto;
        font: 14px/1.6 system-ui, sans-serif;
        color: #0f172a;
        background: #fff;
      }
      h1 { font-size: 1.75rem; }
      h2 {
        font-size: 1.25rem;
        margin-top: 2rem;
        padding-bottom: .35rem;
        border-bottom: 1px solid #e2e8f0;
      }
      table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        margin-top: 12px;
        font-size: .95rem;
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        overflow: hidden;
      }
      thead th {
        text-align: left;
        font-weight: 600;
        background: #f1f5f9;
        border-bottom: 1px solid #e2e8f0;
        padding: .6rem .75rem;
      }
      tbody td {
        padding: .55rem .75rem;
        border-bottom: 1px solid #f1f5f9;
        vertical-align: top;
        word-break: break-word;
      }
      tbody tr:last-child td { border-bottom: 0; }
      tbody tr:nth-child(odd) td { background: #f8fafc; }
    </style>
  </head>
  <body>
    <h1>RABiTS Sample Results</h1>
    <p><b>Sample ID:</b> {{ sample_id }}</p>
    {% if caerbannog_sample_results %}
    <h2>RABiTS Sample Results</h2>
    <table>
        <thead>
            <tr>
                <th>Threat</th>
                <th>Severity</th>
                <th>Threat Assessment</th>
                <th>Confidence</th>
                <th>Description</th>
            </tr>
        </thead>
        <tbody>
            {% for row in caerbannog_sample_results %}
                <tr>
                    {% for k,v in row.items() %}
                        <td>{{ v }}</td>
                    {% endfor %}
                </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}
    {% if caerbannog_cleared_threats %}
    <h2>RABiTS Cleared Threats</h2>
    <table>
        <thead>
            <tr>
                <th>Threat</th>
                <th>Severity</th>
                <th>Threat Assessment</th>
                <th>Confidence</th>
                <th>Description</th>
            </tr>
        </thead>
        <tbody>
            {% for row in caerbannog_cleared_threats %}
                <tr>
                    {% for k,v in row.items() %}
                        <td>{{ v }}</td>
                    {% endfor %}
                </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}
  </body>
</html>
"""


def render_report_html(active, cleared, sample_id):
    """Render the TEMPORARY self-contained HTML sample-results report.

    TODO(#363): LOUD WARNING - rendering a report inside the ETL is a stopgap
    for the demo and is explicitly NOT the long-term design. The snippet markup
    is duplicated from the bactopia report template; the durable path is a
    dedicated reporting component that queries the crawlable result_caerbannog_*
    tables via Athena. When that lands (a later branch): delete REPORT_TEMPLATE
    + this helper, drop the report write below, and remove jinja2 from the
    caerbannog-results job's pymodules. The write location (result-clean) is
    likewise temporary and moves with the report path.
    """
    return Template(REPORT_TEMPLATE).render(
        sample_id=sample_id,
        caerbannog_sample_results=active,
        caerbannog_cleared_threats=cleared,
    )


archive_obj_key = etl_job.parameters["OBJECT_KEY"]

# recover the input-clean sink prefix from the object key and reuse it verbatim
# so result-clean partitions line up with input-clean (see parse_sink_prefix).
sink_prefix = parse_sink_prefix(archive_obj_key, ROOT_PREFIX)

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

# map member basename -> full member name so we can resolve the files named in
# result_meta.json regardless of any directory nesting in the archive.
members_by_basename = {}
for member_name in tf.getnames():
    basename = member_name.rsplit("/", 1)[-1]
    if basename:
        members_by_basename[basename] = member_name


def _read_member(basename, described_as):
    """Extract one archive member's bytes by basename, or fail visibly."""
    member_name = members_by_basename.get(basename)
    if member_name is None:
        msg = (
            f"Caerbannog result archive {archive_obj_key} is missing its "
            f"{described_as} member '{basename}'."
        )
        etl_job.logger.error(msg)
        raise FileNotFoundError(msg)
    with tf.extractfile(member_name) as br:
        return member_name, br.read()


# result_meta.json drives everything: it names the stoplight/cluster members.
_meta_member, meta_bytes = _read_member(META_OBJ, "delivery metadata")
try:
    meta = json.loads(meta_bytes)
except (json.JSONDecodeError, ValueError) as err:
    msg = f"Caerbannog {META_OBJ} in {archive_obj_key} is not valid JSON: {err}"
    etl_job.logger.error(msg)
    raise ValueError(msg) from err

sample_id = meta.get("sample_id", "")
stoplight_member = _read_member(meta["stoplight"], "stoplight")
cluster_member = _read_member(meta["cluster_estimates"], "cluster-estimates")

# stoplight -> CSV (crawler-friendly), keyed by the sink prefix.
stoplight_rows = _json_outputs_to_rows([stoplight_member], normalize_stoplight)
stoplight_key = "/".join([STOPLIGHT_TABLE, sink_prefix, "stoplight.csv"])
print(f"Writing stoplight output to {stoplight_key}")
etl_job.write_sink_file(
    _rows_to_csv(stoplight_rows, STOPLIGHT_COLUMNS), stoplight_key
)

# cluster-estimates -> CSV (crawler-friendly), keyed by the sink prefix.
cluster_rows = _json_outputs_to_rows(
    [cluster_member], normalize_cluster_estimates
)
cluster_key = "/".join([CLUSTER_TABLE, sink_prefix, "cluster_estimates.csv"])
print(f"Writing cluster-estimates output to {cluster_key}")
etl_job.write_sink_file(
    _rows_to_csv(cluster_rows, CLUSTER_COLUMNS), cluster_key
)

# TEMPORARY (TODO(#363), see render_report_html): render a self-contained HTML
# sample-results report from the stoplight rows and write it under the
# crawler-excluded report prefix. This does not belong in the ETL and moves out
# to a dedicated reporting path later.
active_rows, cleared_rows = stoplight_report_rows(stoplight_rows)
report_html = render_report_html(active_rows, cleared_rows, sample_id)
report_key = "/".join([REPORT_PREFIX, sink_prefix, "report.html"])
print(f"Writing TEMPORARY caerbannog report to {report_key}")
etl_job.write_sink_file(report_html, report_key)
