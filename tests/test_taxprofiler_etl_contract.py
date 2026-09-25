"""Contract tests for the taxprofiler Kraken2 Glue ETL adapter."""

import csv
import hashlib
import importlib.util
import io
import os
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "taxprofiler-kraken2"


def _load_etl(monkeypatch, module_name, object_key, source):
    class FakeEtlJob:
        last = None

        def __init__(self):
            self.parameters = {
                "OBJECT_KEY": object_key,
                "SRC_BUCKET_NAME": "example-result-raw",
                "SINK_BUCKET_NAME": "example-result-clean",
            }
            self._source = source
            self.writes = []
            FakeEtlJob.last = self

        def get_src_file(self):
            return self._source

        def write_sink_file(self, content, key):
            self.writes.append((key, content))

    capepy_module = types.ModuleType("capepy")
    capepy_module.__path__ = []
    aws_module = types.ModuleType("capepy.aws")
    aws_module.__path__ = []
    glue_module = types.ModuleType("capepy.aws.glue")
    setattr(glue_module, "EtlJob", FakeEtlJob)
    setattr(capepy_module, "aws", aws_module)
    setattr(aws_module, "glue", glue_module)

    def fake_exit(code):
        raise SystemExit(code)

    monkeypatch.setattr(os, "_exit", fake_exit)
    monkeypatch.setitem(sys.modules, "capepy", capepy_module)
    monkeypatch.setitem(sys.modules, "capepy.aws", aws_module)
    monkeypatch.setitem(sys.modules, "capepy.aws.glue", glue_module)

    path = REPO_ROOT / "assets" / "etl" / "etl_taxprofiler_results.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, FakeEtlJob.last


def _read_fixture(relative_path):
    return (FIXTURE_ROOT / relative_path).read_bytes()


def _csv_writes(fake_job):
    keys = [key for key, _ in fake_job.writes]
    assert len(keys) == len(set(keys))
    return {
        key: list(csv.reader(io.StringIO(content)))
        for key, content in fake_job.writes
    }


@pytest.mark.parametrize("layout_prefix", ["output/", ""])
def test_kraken_report_writes_rows_and_summary(monkeypatch, layout_prefix):
    object_key = (
        "taxprofiler-output/btk-release-live-20260924151922/"
        + layout_prefix
        + "kraken2/standard-8/"
        "btk-release-live-20260924151922_btk-release-live-20260924151922_"
        "standard-8.kraken2.kraken2.report.txt"
    )
    _, fake_job = _load_etl(
        monkeypatch,
        "etl_taxprofiler_kraken_report_test",
        object_key,
        _read_fixture(
            "output/kraken2/standard-8/"
            "btk-release-live-20260924151922_btk-release-live-20260924151922_"
            "standard-8.kraken2.kraken2.report.txt"
        ),
    )

    writes = _csv_writes(fake_job)
    taxa_key = (
        "kraken2_taxa/sample_id=btk-release-live-20260924151922/"
        "database_id=standard-8/taxa.csv"
    )
    summary_key = (
        "kraken2_summary/sample_id=btk-release-live-20260924151922/"
        "database_id=standard-8/summary.csv"
    )

    assert set(writes) == {taxa_key, summary_key}
    assert writes[taxa_key][0] == [
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
    assert len(writes[taxa_key]) == 1309
    assert writes[taxa_key][1][4:6] == ["U", "U"]
    assert writes[taxa_key][-1][4:6] == ["S1", "S"]
    assert writes[summary_key][0][-1] == "report_row_count"
    assert writes[summary_key][1][0:2] == ["391912", "248629"]
    assert float(writes[summary_key][1][2]) == pytest.approx(63.44000694033355)
    assert writes[summary_key][1][3] == "143283"
    assert float(writes[summary_key][1][4]) == pytest.approx(36.55999305966645)
    assert writes[summary_key][1][5] == "1306"
    assert writes[summary_key][1][6] == "Bacillus thuringiensis"
    assert writes[summary_key][1][7:11] == ["1428", "11.94", "46804", "1308"]
    assert hashlib.sha256(
        _read_fixture(
            "output/kraken2/standard-8/"
            "btk-release-live-20260924151922_btk-release-live-20260924151922_"
            "standard-8.kraken2.kraken2.report.txt"
        )
    ).hexdigest() == (
        "55b371480d082c4c4088b78f9c7d424b5b135965aae61a45a5b314879e46cbfd"
    )


@pytest.mark.parametrize("layout_prefix", ["output/", ""])
@pytest.mark.parametrize(
    ("relative_path", "object_key_suffix", "expected_key", "expected_header"),
    [
        (
            "output/multiqc/multiqc_data/multiqc_general_stats.txt",
            "output/multiqc/multiqc_data/multiqc_general_stats.txt",
            "taxprofiler_multiqc_general_stats/sample_id=btk-release-live-20260924151922/stats.csv",
            ["metric", "value"],
        ),
        (
            "output/multiqc/multiqc_data/multiqc_kraken.txt",
            "output/multiqc/multiqc_data/multiqc_kraken.txt",
            "taxprofiler_multiqc_kraken/sample_id=btk-release-live-20260924151922/rank_summary.csv",
            ["rank", "taxon_name", "reads"],
        ),
        (
            "output/multiqc/multiqc_data/kraken-top-n-plot_Species.txt",
            "output/multiqc/multiqc_data/kraken-top-n-plot_Species.txt",
            "taxprofiler_multiqc_plots/sample_id=btk-release-live-20260924151922/plot=Species/plot.csv",
            ["plot_rank", "category", "value"],
        ),
        (
            "output/multiqc/multiqc_data/multiqc_software_versions.txt",
            "output/multiqc/multiqc_data/multiqc_software_versions.txt",
            "taxprofiler_versions/sample_id=btk-release-live-20260924151922/source_kind=multiqc/versions.csv",
            ["scope", "tool", "version"],
        ),
        (
            "output/pipeline_info/nf_core_taxprofiler_software_mqc_versions.yml",
            "output/pipeline_info/nf_core_taxprofiler_software_mqc_versions.yml",
            "taxprofiler_versions/sample_id=btk-release-live-20260924151922/source_kind=pipeline/versions.csv",
            ["scope", "tool", "version"],
        ),
        (
            "output/pipeline_info/params_2026-09-24_15-48-16.json",
            "output/pipeline_info/params_2026-09-24_15-48-16.json",
            "taxprofiler_params/sample_id=btk-release-live-20260924151922/source_file=params_2026-09-24_15-48-16/params.csv",
            ["parameter", "value", "value_type"],
        ),
        (
            "output/pipeline_info/execution_trace_2026-09-24_15-47-56.txt",
            "output/pipeline_info/execution_trace_2026-09-24_15-47-56.txt",
            "taxprofiler_processes/sample_id=btk-release-live-20260924151922/source_file=execution_trace_2026-09-24_15-47-56/processes.csv",
            [
                "task_id",
                "hash",
                "native_id",
                "name",
                "status",
                "exit_code",
                "submitted_at",
                "duration",
                "realtime",
                "cpu_percent",
                "peak_rss",
                "peak_vmem",
                "read_bytes",
                "written_bytes",
            ],
        ),
        (
            "output/pipeline_info/execution_report_2026-09-24_15-47-56.html",
            "output/pipeline_info/execution_report_2026-09-24_15-47-56.html",
            "taxprofiler_run_metadata/sample_id=btk-release-live-20260924151922/run_metadata.csv",
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
        ),
    ],
)
def test_taxprofiler_metadata_outputs(
    monkeypatch,
    relative_path,
    object_key_suffix,
    expected_key,
    expected_header,
    layout_prefix,
):
    object_key = (
        "taxprofiler-output/btk-release-live-20260924151922/"
        + layout_prefix
        + object_key_suffix.removeprefix("output/")
    )
    _, fake_job = _load_etl(
        monkeypatch,
        f"etl_taxprofiler_{Path(relative_path).stem.replace('-', '_')}_test",
        object_key,
        _read_fixture(relative_path),
    )

    writes = _csv_writes(fake_job)
    assert list(writes) == [expected_key]
    assert writes[expected_key][0] == expected_header
    assert len(writes[expected_key]) > 1


def test_multiqc_json_is_flattened(monkeypatch):
    object_key = (
        "taxprofiler-output/btk-release-live-20260924151922/"
        "output/multiqc/multiqc_data/multiqc_data.json"
    )
    _, fake_job = _load_etl(
        monkeypatch,
        "etl_taxprofiler_multiqc_json_test",
        object_key,
        _read_fixture("output/multiqc/multiqc_data/multiqc_data.json"),
    )

    writes = _csv_writes(fake_job)
    key = (
        "taxprofiler_multiqc_json/sample_id=btk-release-live-20260924151922/"
        "multiqc_data.csv"
    )
    assert list(writes) == [key]
    assert writes[key][0] == ["json_path", "value", "value_type"]
    assert ["report_general_stats_data.kraken", "", "dict"] not in writes[key]
    assert any(row[0].endswith("pct_top_one") for row in writes[key][1:])


def test_unmatched_object_is_a_successful_noop(monkeypatch):
    with pytest.raises(SystemExit) as error:
        _load_etl(
            monkeypatch,
            "etl_taxprofiler_ignored_test",
            "taxprofiler-output/sample/output/multiqc/multiqc_report.html",
            b"not parsed",
        )
    assert error.value.code == 0


def test_malformed_kraken_report_fails_clearly(monkeypatch):
    object_key = (
        "taxprofiler-output/sample/output/kraken2/standard-8/"
        "sample.kraken2.kraken2.report.txt"
    )
    with pytest.raises(ValueError, match="Malformed Kraken2 report"):
        _load_etl(
            monkeypatch,
            "etl_taxprofiler_malformed_test",
            object_key,
            b"not-a-report\n",
        )
