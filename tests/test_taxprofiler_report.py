"""Tests for the taxprofiler Kraken2 Athena report data function."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = REPO_ROOT / "assets" / "report" / "taxprofiler-kraken2"


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def iterrows(self):
        for index, row in enumerate(self.rows):
            yield index, row

    @property
    def empty(self):
        return not self.rows


def _load_report(monkeypatch, rows):
    captured = {}

    class FakeAthenaClient:
        def list_data_catalogs(self):
            return {"DataCatalogsSummary": [{"CatalogName": "AwsDataCatalog"}]}

        def list_databases(self, CatalogName):
            assert CatalogName == "AwsDataCatalog"
            return {"DatabaseList": [{"Name": "seqauto-catalog-test"}]}

        def list_work_groups(self):
            return {"WorkGroups": [{"Name": "ccd-dlh-athena-wrkgrp-test"}]}

    class FakeBoto3:
        def client(self, name):
            assert name == "athena"
            return FakeAthenaClient()

    def read_sql_query(**kwargs):
        captured.update(kwargs)
        return FakeFrame(rows)

    wr_module = types.ModuleType("awswrangler")
    setattr(
        wr_module,
        "athena",
        types.SimpleNamespace(read_sql_query=read_sql_query),
    )
    boto3_module = types.ModuleType("boto3")
    setattr(boto3_module, "client", FakeBoto3().client)
    monkeypatch.setitem(sys.modules, "awswrangler", wr_module)
    monkeypatch.setitem(sys.modules, "boto3", boto3_module)

    path = REPORT_DIR / "data_function.py"
    spec = importlib.util.spec_from_file_location(
        "taxprofiler_report_data_function", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load data function from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, captured


def _rows():
    return [
        {
            "database_id": "standard-8",
            "source_row": 0,
            "percent": 36.56,
            "clade_reads": 143283,
            "direct_reads": 143283,
            "rank": "U",
            "rank_base": "U",
            "taxid": "0",
            "taxon_name": "unclassified",
            "depth": 0,
        },
        {
            "database_id": "standard-8",
            "source_row": 1,
            "percent": 63.44,
            "clade_reads": 248629,
            "direct_reads": 13478,
            "rank": "R",
            "rank_base": "R",
            "taxid": "1",
            "taxon_name": "root",
            "depth": 0,
        },
        {
            "database_id": "standard-8",
            "source_row": 2,
            "percent": 11.94,
            "clade_reads": 46804,
            "direct_reads": 44428,
            "rank": "S",
            "rank_base": "S",
            "taxid": "1428",
            "taxon_name": "Bacillus thuringiensis",
            "depth": 5,
        },
        {
            "database_id": "standard-8",
            "source_row": 3,
            "percent": 0.2,
            "clade_reads": 778,
            "direct_reads": 778,
            "rank": "S1",
            "rank_base": "S",
            "taxid": "29339",
            "taxon_name": "Bacillus thuringiensis serovar kurstki",
            "depth": 6,
        },
    ]


def test_data_function_queries_taxa_with_safe_parameters(monkeypatch):
    module, captured = _load_report(monkeypatch, _rows())

    data = module.data_function(
        {"sample_id": "btk-release-live-20260924151922"}, None
    )

    assert captured["database"] == "seqauto-catalog-test"
    assert captured["ctas_approach"] is False
    assert captured["paramstyle"] == "qmark"
    assert captured["params"] == [
        "btk-release-live-20260924151922",
        "standard-8",
    ]
    assert captured["workgroup"] == "ccd-dlh-athena-wrkgrp-test"
    assert captured["data_source"] == "AwsDataCatalog"
    assert '"seqauto-catalog-test"."result_kraken2_taxa"' in captured["sql"]
    assert data["summary"]["total_reads"] == 391912
    assert data["summary"]["classified_reads"] == 248629
    assert data["summary"]["unclassified_reads"] == 143283
    assert data["summary"]["top_species"]["name"] == "Bacillus thuringiensis"
    assert data["top_species"][0]["taxid"] == "1428"
    assert "Bacillus thuringiensis" in data["tree_html"]
    assert 'data-default="closed"' in data["tree_html"]


def test_data_function_rejects_unsafe_sample_id(monkeypatch):
    module, _ = _load_report(monkeypatch, _rows())

    with pytest.raises(ValueError, match="Invalid sample id"):
        module.data_function({"sample_id": "sample' OR '1'='1"}, None)


def test_template_renders_legacy_report_shape(monkeypatch):
    module, _ = _load_report(monkeypatch, _rows())
    data = module.data_function({"sample_id": "sample-1"}, None)
    template = Environment(
        loader=FileSystemLoader(str(REPORT_DIR))
    ).get_template("template.html.j2")

    rendered = template.render(data)

    assert "Kraken2 Taxonomic Classification" in rendered
    assert "Total reads" in rendered
    assert "Top species" in rendered
    assert "Full taxonomic breakdown" in rendered
    assert "Relevant" in rendered
    assert "Bacillus thuringiensis" in rendered
