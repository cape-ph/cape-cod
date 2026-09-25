"""Retrieve normalized taxprofiler Kraken2 data for the report."""

import html
import logging
import math
import re
from typing import Any

import awswrangler as wr
import boto3

logger = logging.getLogger()
logger.setLevel("INFO")

SAMPLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
DATABASE_ID = "standard-8"
TAXA_QUERY = """
select
    database_id,
    source_row,
    percent,
    clade_reads,
    direct_reads,
    rank,
    rank_base,
    taxid,
    taxon_name,
    depth
from
    "{database}"."result_kraken2_taxa"
where
    sample_id = ?
    and database_id = ?
order by source_row
"""

RANK_LABELS = {
    "U": "Unclassified",
    "R": "Root",
    "D": "Domain",
    "K": "Kingdom",
    "P": "Phylum",
    "C": "Class",
    "O": "Order",
    "F": "Family",
    "G": "Genus",
    "S": "Species",
}
DEFAULT_OPEN_PCT = 1.0
INDENT_PX = 16


def _validate_sample_id(sample_id):
    if not isinstance(sample_id, str) or not SAMPLE_ID_PATTERN.fullmatch(
        sample_id
    ):
        raise ValueError("Invalid sample id for taxprofiler report")
    return sample_id


def _find_seqauto_database():
    athena = boto3.client("athena")
    catalogs = athena.list_data_catalogs().get("DataCatalogsSummary", [])
    catalog_names = [item["CatalogName"] for item in catalogs]
    if "AwsDataCatalog" in catalog_names:
        catalog = "AwsDataCatalog"
    elif len(catalog_names) == 1:
        catalog = catalog_names[0]
    else:
        raise ValueError("Could not resolve the Athena data catalog")

    databases = athena.list_databases(CatalogName=catalog).get(
        "DatabaseList", []
    )
    matches = [
        database["Name"]
        for database in databases
        if "seqauto-catalog" in database.get("Name", "")
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one seqauto Glue database, found {len(matches)}"
        )

    workgroups = athena.list_work_groups().get("WorkGroups", [])
    workgroup_matches = [
        workgroup["Name"]
        for workgroup in workgroups
        if "athena-wrkgrp" in workgroup.get("Name", "")
    ]
    if len(workgroup_matches) != 1:
        raise ValueError(
            "Expected one CAPE Athena workgroup, "
            f"found {len(workgroup_matches)}"
        )
    return catalog, matches[0], workgroup_matches[0]


def _python_value(value: Any):
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _as_int(value: Any, field: str):
    if value is None:
        raise ValueError(f"Taxprofiler Athena row is missing {field}")
    try:
        return int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Taxprofiler Athena row has invalid {field}"
        ) from error


def _as_float(value: Any, field: str):
    if value is None:
        raise ValueError(f"Taxprofiler Athena row is missing {field}")
    try:
        return float(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Taxprofiler Athena row has invalid {field}"
        ) from error


def _as_text(value: Any, field: str):
    if value is None:
        raise ValueError(f"Taxprofiler Athena row is missing {field}")
    return str(value)


def _records_from_frame(frame):
    records = []
    for _, row in frame.iterrows():
        values = {
            key: _python_value(row[key])
            for key in (
                "database_id",
                "source_row",
                "percent",
                "clade_reads",
                "direct_reads",
                "rank",
                "rank_base",
                "taxid",
                "taxon_name",
                "depth",
            )
        }
        records.append(
            {
                "database_id": _as_text(values["database_id"], "database_id"),
                "source_row": _as_int(values["source_row"], "source_row"),
                "percent": _as_float(values["percent"], "percent"),
                "clade_reads": _as_int(values["clade_reads"], "clade_reads"),
                "direct_reads": _as_int(values["direct_reads"], "direct_reads"),
                "rank": _as_text(values["rank"], "rank"),
                "rank_base": _as_text(values["rank_base"], "rank_base"),
                "taxid": _as_text(values["taxid"], "taxid"),
                "taxon_name": _as_text(values["taxon_name"], "taxon_name"),
                "depth": _as_int(values["depth"], "depth"),
            }
        )
    return records


def _summary(rows):
    unclassified = next((row for row in rows if row["rank"] == "U"), None)
    root = next((row for row in rows if row["rank"] == "R"), None)
    classified_reads = root["clade_reads"] if root else 0
    unclassified_reads = unclassified["clade_reads"] if unclassified else 0
    total_reads = classified_reads + unclassified_reads
    species = [row for row in rows if row["rank"] == "S"]
    top = max(species, key=lambda row: row["clade_reads"], default=None)

    def pct(value):
        return 100.0 * value / total_reads if total_reads else 0.0

    return {
        "total_reads": total_reads,
        "classified_reads": classified_reads,
        "classified_pct": pct(classified_reads),
        "unclassified_reads": unclassified_reads,
        "unclassified_pct": pct(unclassified_reads),
        "distinct_taxa": sum(row["rank"] not in ("U", "R") for row in rows),
        "top_species": (
            {
                "name": html.escape(top["taxon_name"]),
                "pct": top["percent"],
                "clade_reads": top["clade_reads"],
                "taxid": html.escape(top["taxid"]),
            }
            if top
            else None
        ),
    }


def _top_species(rows, limit=15):
    species = [row for row in rows if row["rank"] == "S"]
    species.sort(key=lambda row: row["clade_reads"], reverse=True)
    return [
        {
            "name": html.escape(row["taxon_name"]),
            "pct": row["percent"],
            "clade_reads": row["clade_reads"],
            "taxid": html.escape(row["taxid"]),
        }
        for row in species[:limit]
    ]


def _build_tree(rows):
    roots = []
    stack = []
    for row in rows:
        node = dict(row, children=[])
        while stack and stack[-1]["depth"] >= node["depth"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


def _default_open(node):
    if node["rank_base"] == "S":
        return False
    return node["percent"] >= DEFAULT_OPEN_PCT


def _row_cells(node, toggle):
    pad = node["depth"] * INDENT_PX
    caret_class = "caret" if toggle else "caret spacer"
    name = html.escape(node["taxon_name"])
    rank = html.escape(node["rank"])
    rank_label = html.escape(
        str(RANK_LABELS.get(node["rank_base"], node["rank"]))
    )
    taxid = html.escape(node["taxid"])
    return (
        f'<span class="c-name" style="padding-left:{pad}px">'
        f'<span class="{caret_class}"></span>'
        f'<span class="name">{name}</span></span>'
        f'<span><span class="rank-badge" title="{rank_label}">{rank}</span>'
        f"</span>"
        f'<span class="c-num">{node["percent"]:.2f}</span>'
        f'<span class="c-num">{node["clade_reads"]:,}</span>'
        f'<span class="c-num">{node["direct_reads"]:,}</span>'
        f'<span class="c-num">{taxid}</span>'
    )


def _render_node(node):
    children = node["children"]
    if not children:
        return f'<div class="row">{_row_cells(node, toggle=False)}</div>'
    is_open = _default_open(node)
    open_attr = " open" if is_open else ""
    default_state = "open" if is_open else "closed"
    inner = "".join(_render_node(child) for child in children)
    return (
        f'<details class="node" data-default="{default_state}"{open_attr}>'
        f'<summary class="row">{_row_cells(node, toggle=True)}</summary>'
        f'<div class="children">{inner}</div></details>'
    )


def _render_tree(rows):
    return "".join(_render_node(node) for node in _build_tree(rows))


def data_function(event, context):
    """Return data required by the taxprofiler Kraken2 report."""
    sample_id = _validate_sample_id(event.get("sample_id"))
    catalog, database, workgroup = _find_seqauto_database()
    frame = wr.athena.read_sql_query(
        sql=TAXA_QUERY.format(database=database),
        database=database,
        ctas_approach=False,
        params=[sample_id, DATABASE_ID],
        paramstyle="qmark",
        workgroup=workgroup,
        data_source=catalog,
    )
    rows = _records_from_frame(frame)
    if not rows:
        raise ValueError(
            f"No taxprofiler Kraken2 data found for sample {sample_id}"
        )
    database_ids = {row["database_id"] for row in rows}
    if len(database_ids) != 1:
        raise ValueError(
            f"Expected one taxprofiler database for sample {sample_id}, "
            f"found {sorted(database_ids)}"
        )

    return {
        "sample_id": html.escape(sample_id),
        "summary": _summary(rows),
        "top_species": _top_species(rows),
        "tree_html": _render_tree(rows),
        "has_taxa": bool(rows),
    }
