"""ETL adapters for taxprofiler Kraken2 output."""

import ast
import csv
import html
import io
import json
import os
import re
from pathlib import PurePosixPath

import yaml
from capepy.aws.glue import EtlJob

etl_job = EtlJob()

OUTPUT_PREFIX = "taxprofiler-output"
SAMPLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
TAXA_COLUMNS = [
    "source_row",
    "percent",
    "clade_reads",
    "direct_reads",
    "rank",
    "rank_base",
    "taxid",
    "taxon_name",
    "depth",
]
SUMMARY_COLUMNS = [
    "total_reads",
    "classified_reads",
    "classified_percent",
    "unclassified_reads",
    "unclassified_percent",
    "distinct_taxa",
    "top_species_name",
    "top_species_taxid",
    "top_species_percent",
    "top_species_clade_reads",
    "report_row_count",
]


def _safe_component(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))


def _csv_text(headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _write_csv(key, headers, rows):
    etl_job.write_sink_file(_csv_text(headers, rows), key)


def _context(object_key):
    parts = object_key.split("/")
    if len(parts) < 3 or parts[0] != OUTPUT_PREFIX or not parts[1]:
        return None
    if not SAMPLE_ID_PATTERN.fullmatch(parts[1]):
        raise ValueError(f"Invalid taxprofiler sample id: {parts[1]}")
    return {
        "sample_id": parts[1],
        "relative_key": "/".join(parts[2:]),
        "filename": parts[-1],
        "database_id": (
            parts[4]
            if len(parts) > 5 and parts[2:4] == ["output", "kraken2"]
            else None
        ),
        "source_key": object_key,
    }


def _classify(object_key):
    context = _context(object_key)
    if context is None:
        return None, None

    relative_key = context["relative_key"]
    filename = context["filename"]

    if relative_key.startswith("output/kraken2/") and filename.endswith(
        ".kraken2.report.txt"
    ):
        return "kraken_report", context
    if relative_key.endswith("output/multiqc/multiqc_data/multiqc_data.json"):
        return "multiqc_json", context
    if relative_key.endswith(
        "output/multiqc/multiqc_data/multiqc_general_stats.txt"
    ):
        return "multiqc_general_stats", context
    if relative_key.endswith("output/multiqc/multiqc_data/multiqc_kraken.txt"):
        return "multiqc_kraken", context
    if (
        relative_key.startswith("output/multiqc/multiqc_data/")
        and filename.startswith("kraken-top-n-plot_")
        and filename.endswith(".txt")
    ):
        return "multiqc_plot", context
    if relative_key.endswith(
        "output/multiqc/multiqc_data/multiqc_software_versions.txt"
    ):
        return "multiqc_versions", context
    if (
        relative_key.startswith("output/pipeline_info/")
        and filename.startswith("params_")
        and filename.endswith(".json")
    ):
        return "params", context
    if (
        relative_key.startswith("output/pipeline_info/")
        and filename.startswith("execution_trace_")
        and filename.endswith(".txt")
    ):
        return "execution_trace", context
    if (
        relative_key.startswith("output/pipeline_info/")
        and filename.startswith("nf_core_taxprofiler_software_mqc_versions")
        and filename.endswith(".yml")
    ):
        return "pipeline_versions", context
    if (
        relative_key.startswith("output/pipeline_info/")
        and filename.startswith("execution_report_")
        and filename.endswith(".html")
    ):
        return "execution_report", context
    return None, context


def _partition_prefix(context, table, extra=None):
    parts = [table, f"sample_id={_safe_component(context['sample_id'])}"]
    if context.get("database_id"):
        parts.append(f"database_id={_safe_component(context['database_id'])}")
    if extra:
        parts.extend(f"{key}={_safe_component(value)}" for key, value in extra)
    return "/".join(parts)


def _parse_kraken_report(source_bytes):
    rows = []
    malformed = []
    for source_row, line in enumerate(
        source_bytes.decode("utf-8").splitlines()
    ):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 6:
            malformed.append(source_row)
            continue
        try:
            percent = float(parts[0])
            clade_reads = int(parts[1])
            direct_reads = int(parts[2])
        except ValueError:
            malformed.append(source_row)
            continue

        rank = parts[3].strip()
        raw_name = parts[5]
        rows.append(
            {
                "source_row": source_row,
                "percent": percent,
                "clade_reads": clade_reads,
                "direct_reads": direct_reads,
                "rank": rank,
                "rank_base": rank[:1],
                "taxid": parts[4].strip(),
                "taxon_name": raw_name.strip(),
                "depth": (len(raw_name) - len(raw_name.lstrip(" "))) // 2,
            }
        )

    if malformed:
        raise ValueError(
            "Malformed Kraken2 report rows at source lines: "
            + ", ".join(str(line) for line in malformed[:10])
        )
    if not rows:
        raise ValueError("Taxprofiler Kraken2 report is empty")
    return rows


def _summary_row(rows):
    unclassified = next((row for row in rows if row["rank"] == "U"), None)
    root = next((row for row in rows if row["rank"] == "R"), None)
    classified_reads = root["clade_reads"] if root else 0
    unclassified_reads = unclassified["clade_reads"] if unclassified else 0
    total_reads = classified_reads + unclassified_reads
    species = [row for row in rows if row["rank"] == "S"]
    top_species = max(species, key=lambda row: row["clade_reads"], default=None)

    def percentage(value):
        return 100.0 * value / total_reads if total_reads else 0.0

    return [
        total_reads,
        classified_reads,
        percentage(classified_reads),
        unclassified_reads,
        percentage(unclassified_reads),
        sum(row["rank"] not in ("U", "R") for row in rows),
        top_species["taxon_name"] if top_species else "",
        top_species["taxid"] if top_species else "",
        top_species["percent"] if top_species else 0.0,
        top_species["clade_reads"] if top_species else 0,
        len(rows),
    ]


def _parse_multiqc_general_stats(source_bytes):
    rows = list(
        csv.reader(io.StringIO(source_bytes.decode("utf-8")), delimiter="\t")
    )
    if len(rows) < 2 or len(rows[1]) != len(rows[0]):
        raise ValueError("Invalid Taxprofiler MultiQC general stats shape")
    return [
        [metric, value]
        for metric, value in zip(rows[0][1:], rows[1][1:])
        if metric and value
    ]


def _parse_multiqc_kraken(source_bytes):
    rows = list(
        csv.reader(io.StringIO(source_bytes.decode("utf-8")), delimiter="\t")
    )
    if len(rows) < 2:
        raise ValueError("Taxprofiler MultiQC Kraken output is empty")

    output = []
    for row in rows[1:]:
        if len(row) != len(rows[0]):
            raise ValueError("Invalid Taxprofiler MultiQC Kraken shape")
        for rank, raw_values in zip(rows[0][1:], row[1:]):
            if not raw_values:
                continue
            try:
                values = ast.literal_eval(raw_values)
            except (SyntaxError, ValueError) as error:
                raise ValueError(
                    f"Invalid MultiQC Kraken values for rank {rank}"
                ) from error
            if not isinstance(values, dict):
                raise ValueError(
                    f"MultiQC Kraken values for rank {rank} are not a mapping"
                )
            for taxon_name, reads in values.items():
                try:
                    reads = int(float(reads))
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid MultiQC Kraken read count for {taxon_name}"
                    ) from error
                output.append([rank, taxon_name, reads])
    return output


def _parse_multiqc_plot(source_bytes, filename):
    rows = list(
        csv.reader(io.StringIO(source_bytes.decode("utf-8")), delimiter="\t")
    )
    if len(rows) < 2 or len(rows[1]) != len(rows[0]):
        raise ValueError(f"Invalid Taxprofiler MultiQC plot shape: {filename}")
    plot_rank = filename.removeprefix("kraken-top-n-plot_").removesuffix(".txt")
    output = []
    for category, value in zip(rows[0][1:], rows[1][1:]):
        if category and value:
            try:
                value = float(value)
            except ValueError as error:
                raise ValueError(
                    f"Invalid MultiQC plot value for {category}"
                ) from error
            output.append([plot_rank, category, value])
    return output


def _parse_versions_yaml(source_bytes):
    try:
        data = yaml.safe_load(source_bytes) or {}
    except yaml.YAMLError as error:
        raise ValueError(
            "Invalid taxprofiler software versions YAML"
        ) from error
    output = []
    if not isinstance(data, dict):
        raise ValueError("Taxprofiler software versions YAML must be an object")
    for scope, values in data.items():
        if isinstance(values, dict):
            for tool, version in values.items():
                output.append([scope, tool, str(version)])
        elif values is not None:
            output.append([scope, scope, str(values)])
    return output


def _parse_multiqc_versions(source_bytes):
    rows = list(
        csv.reader(io.StringIO(source_bytes.decode("utf-8")), delimiter="\t")
    )
    if len(rows) < 2:
        raise ValueError(
            "Taxprofiler MultiQC software versions output is empty"
        )
    output = []
    for row in rows[1:]:
        if len(row) != len(rows[0]):
            raise ValueError("Invalid Taxprofiler MultiQC software shape")
        scope = row[0] if row else ""
        for tool, version in zip(rows[0][1:], row[1:]):
            if tool and version:
                output.append([scope, tool, version])
    return output


def _parse_params(source_bytes):
    try:
        data = json.loads(source_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid taxprofiler params JSON") from error
    if not isinstance(data, dict):
        raise ValueError("Taxprofiler params JSON must be an object")
    output = []
    for parameter, value in data.items():
        if isinstance(value, bool):
            value_type = "boolean"
        elif isinstance(value, (int, float)):
            value_type = "number"
        elif value is None:
            value_type = "null"
        elif isinstance(value, (dict, list)):
            value_type = "json"
        else:
            value_type = "string"
        serialized = (
            json.dumps(value, sort_keys=True)
            if isinstance(value, (dict, list))
            else "" if value is None else str(value)
        )
        output.append([parameter, serialized, value_type])
    return output


def _parse_execution_trace(source_bytes):
    reader = csv.DictReader(
        io.StringIO(source_bytes.decode("utf-8")), delimiter="\t"
    )
    headers = {
        "task_id": "task_id",
        "hash": "hash",
        "native_id": "native_id",
        "name": "name",
        "status": "status",
        "exit": "exit_code",
        "submit": "submitted_at",
        "duration": "duration",
        "realtime": "realtime",
        "%cpu": "cpu_percent",
        "peak_rss": "peak_rss",
        "peak_vmem": "peak_vmem",
        "rchar": "read_bytes",
        "wchar": "written_bytes",
    }
    if reader.fieldnames is None or any(
        source not in reader.fieldnames for source in headers
    ):
        raise ValueError("Invalid taxprofiler execution trace header")
    output = []
    for row in reader:
        output.append([row.get(source, "") for source in headers])
    if not output:
        raise ValueError("Taxprofiler execution trace is empty")
    return list(headers.values()), output


def _extract_html_field(source, label):
    match = re.search(
        rf"<dt[^>]*>\s*{re.escape(label)}\s*</dt>\s*<dd[^>]*>(.*?)</dd>",
        source,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return ""
    return " ".join(re.sub(r"<[^>]+>", "", match.group(1)).split())


def _parse_execution_report(source_bytes, context):
    source = html.unescape(source_bytes.decode("utf-8"))
    if "Workflow execution completed successfully!" not in source:
        raise ValueError("Taxprofiler execution report does not show success")

    workflow_start_match = re.search(
        r'id="workflow_start">\s*([^<]+)<', source, flags=re.IGNORECASE
    )
    workflow_complete_match = re.search(
        r'id="workflow_complete">\s*([^<]+)<', source, flags=re.IGNORECASE
    )
    workflow_name = _extract_html_field(source, "Workflow name")
    workflow_version = _extract_html_field(source, "Workflow version")
    nextflow_details = _extract_html_field(source, "Nextflow version")
    nextflow_match = re.search(
        r"\bversion\s+([0-9]+(?:\.[0-9]+)+)", nextflow_details
    )
    return [
        context["sample_id"],
        "true",
        workflow_start_match.group(1).strip() if workflow_start_match else "",
        (
            workflow_complete_match.group(1).strip()
            if workflow_complete_match
            else ""
        ),
        workflow_name,
        workflow_version,
        nextflow_match.group(1) if nextflow_match else "",
        context["source_key"],
    ]


def _source_uri(object_key):
    source_bucket = etl_job.parameters.get("SRC_BUCKET_NAME")
    if source_bucket:
        return f"s3://{source_bucket}/{object_key}"
    return object_key


object_key = etl_job.parameters["OBJECT_KEY"]
kind, context = _classify(object_key)
if kind is None:
    print(f"Taxprofiler ETL ignoring {object_key} per configuration.")
    os._exit(0)

source_bytes = etl_job.get_src_file()
context["source_uri"] = _source_uri(object_key)

if kind == "kraken_report":
    taxa_rows = _parse_kraken_report(source_bytes)
    _write_csv(
        f"{_partition_prefix(context, 'kraken2_taxa')}/taxa.csv",
        TAXA_COLUMNS,
        [[row[column] for column in TAXA_COLUMNS] for row in taxa_rows],
    )
    _write_csv(
        f"{_partition_prefix(context, 'kraken2_summary')}/summary.csv",
        SUMMARY_COLUMNS,
        [_summary_row(taxa_rows)],
    )
elif kind == "multiqc_general_stats":
    _write_csv(
        f"{_partition_prefix(context, 'taxprofiler_multiqc_general_stats')}/stats.csv",
        ["metric", "value"],
        _parse_multiqc_general_stats(source_bytes),
    )
elif kind == "multiqc_kraken":
    _write_csv(
        f"{_partition_prefix(context, 'taxprofiler_multiqc_kraken')}/rank_summary.csv",
        ["rank", "taxon_name", "reads"],
        _parse_multiqc_kraken(source_bytes),
    )
elif kind == "multiqc_plot":
    plot_name = (
        context["filename"]
        .removeprefix("kraken-top-n-plot_")
        .removesuffix(".txt")
    )
    _write_csv(
        f"{_partition_prefix(context, 'taxprofiler_multiqc_plots', [('plot', plot_name)])}/plot.csv",
        ["plot_rank", "category", "value"],
        _parse_multiqc_plot(source_bytes, context["filename"]),
    )
elif kind == "multiqc_versions":
    _write_csv(
        f"{_partition_prefix(context, 'taxprofiler_versions', [('source_kind', 'multiqc')])}/versions.csv",
        ["scope", "tool", "version"],
        _parse_multiqc_versions(source_bytes),
    )
elif kind == "pipeline_versions":
    _write_csv(
        f"{_partition_prefix(context, 'taxprofiler_versions', [('source_kind', 'pipeline')])}/versions.csv",
        ["scope", "tool", "version"],
        _parse_versions_yaml(source_bytes),
    )
elif kind == "params":
    source_file = _safe_component(PurePosixPath(context["filename"]).stem)
    _write_csv(
        f"{_partition_prefix(context, 'taxprofiler_params', [('source_file', source_file)])}/params.csv",
        ["parameter", "value", "value_type"],
        _parse_params(source_bytes),
    )
elif kind == "execution_trace":
    source_file = _safe_component(PurePosixPath(context["filename"]).stem)
    headers, rows = _parse_execution_trace(source_bytes)
    _write_csv(
        f"{_partition_prefix(context, 'taxprofiler_processes', [('source_file', source_file)])}/processes.csv",
        headers,
        rows,
    )
elif kind == "execution_report":
    _write_csv(
        f"{_partition_prefix(context, 'taxprofiler_run_metadata')}/run_metadata.csv",
        [
            "sample_id_from_report",
            "workflow_complete",
            "workflow_start",
            "workflow_complete_time",
            "pipeline_name",
            "pipeline_version",
            "nextflow_version",
            "source_key",
        ],
        [_parse_execution_report(source_bytes, context)],
    )
elif kind == "multiqc_json":
    try:
        data = json.loads(source_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid MultiQC data JSON") from error
    if not isinstance(data, dict):
        raise ValueError("MultiQC data JSON must be an object")
    rows = []

    def flatten(value, path):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield from flatten(nested, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            yield path, json.dumps(value, sort_keys=True), "json"
        elif value is None:
            yield path, "", "null"
        else:
            yield path, str(value), type(value).__name__

    for section in ("report_general_stats_data", "report_saved_raw_data"):
        for path, value, value_type in flatten(data.get(section, {}), section):
            rows.append([path, value, value_type])
    _write_csv(
        f"{_partition_prefix(context, 'taxprofiler_multiqc_json')}/multiqc_data.csv",
        ["json_path", "value", "value_type"],
        rows,
    )

print(f"Processed taxprofiler object {object_key} as {kind}.")
