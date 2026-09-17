"""Contract tests for the Bactopia v4 Glue ETL adapters."""

import csv
import importlib.util
import io
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "bactopia-v4"


def _load_etl(monkeypatch, module_name, relative_path, object_key, source):
    class FakeEtlJob:
        last = None

        def __init__(self):
            self.parameters = {"OBJECT_KEY": object_key}
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

    monkeypatch.setitem(sys.modules, "capepy", capepy_module)
    monkeypatch.setitem(sys.modules, "capepy.aws", aws_module)
    monkeypatch.setitem(sys.modules, "capepy.aws.glue", glue_module)

    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, FakeEtlJob.last


def _read_fixture(relative_path):
    return (FIXTURE_ROOT / relative_path).read_bytes()


def _written_csv(fake_job):
    assert len(fake_job.writes) == 1
    key, content = fake_job.writes[0]
    return key, list(csv.reader(io.StringIO(content)))


def test_v4_mlst_adapter_emits_stable_six_column_schema(monkeypatch):
    module, fake_job = _load_etl(
        monkeypatch,
        "etl_bactopia_results_mlst_test",
        "assets/etl/etl_bactopia_results.py",
        "pipeline-output/bactopia-runs/run-1/merged-results/mlst.tsv",
        _read_fixture("merged-results/mlst.tsv"),
    )

    key, rows = _written_csv(fake_job)

    assert module.OUTPUT_ADAPTER.__class__.__name__ == (
        "BactopiaOutputContractV1Adapter"
    )
    assert module.OUTPUT_ADAPTER.MLST_INPUT_HEADER == (
        "FILE",
        "SCHEME",
        "ST",
        "STATUS",
        "SCORE",
        "ALLELES",
    )
    assert module.OUTPUT_ADAPTER.MLST_OUTPUT_HEADER == (
        "file",
        "scheme",
        "st",
        "status",
        "score",
        "alleles",
    )
    assert key == "mlst/bactopia_run=run-1/mlst.csv"
    assert rows == [
        ["file", "scheme", "st", "status", "score", "alleles"],
        [
            "sample/main/assembly/sample.fasta",
            "ecoli_achtman_4",
            "42",
            "PASS",
            "1.0",
            "adk_1;fumC_1;gyrB_1",
        ],
    ]


def test_v4_mlst_adapter_rejects_schema_changes(monkeypatch):
    with pytest.raises(
        ValueError, match="Unexpected output contract v1 MLST header"
    ):
        _load_etl(
            monkeypatch,
            "etl_bactopia_results_mlst_schema_test",
            "assets/etl/etl_bactopia_results.py",
            "pipeline-output/bactopia-runs/run-1/merged-results/mlst.tsv",
            b"FILE\tSCHEME\tST\tSTATUS\tSCORE\tWRONG\n",
        )


def test_v4_amrfinder_adapter_normalizes_report_columns(monkeypatch):
    _, fake_job = _load_etl(
        monkeypatch,
        "etl_bactopia_results_amrfinder_test",
        "assets/etl/etl_bactopia_results.py",
        "pipeline-output/bactopia-runs/run-1/merged-results/amrfinderplus.tsv",
        _read_fixture("merged-results/amrfinderplus.tsv"),
    )

    key, rows = _written_csv(fake_job)

    assert key == "amrfinderplus/bactopia_run=run-1/amrfinderplus.csv"
    assert rows[0] == [
        "element_symbol",
        "element_name",
        "scope",
        "subtype",
        "class",
        "subclass",
        "type",
        "method",
        "%_coverage_of_reference",
        "%_identity_to_reference",
    ]
    assert rows[1][0:2] == ["blaTEM", "TEM beta-lactamase"]


@pytest.mark.parametrize(
    ("relative_path", "object_key", "table_name", "delimiter"),
    [
        (
            "sample/main/assembler/sample.tsv",
            "pipeline-output/bactopia-runs/run-1/sample/main/assembler/sample.tsv",
            "assembler",
            "\t",
        ),
        (
            "sample/main/sketcher/sample-mash-refseq88-k21.txt",
            (
                "pipeline-output/bactopia-runs/run-1/sample/main/sketcher/"
                "sample-mash-refseq88-k21.txt"
            ),
            "mash-refseq88-k21",
            "\t",
        ),
        (
            "sample/main/sketcher/sample-sourmash-gtdb-rs207-k31.txt",
            (
                "pipeline-output/bactopia-runs/run-1/sample/main/sketcher/"
                "sample-sourmash-gtdb-rs207-k31.txt"
            ),
            "sourmash-gtdb-rs207-k31",
            ",",
        ),
    ],
)
def test_v4_sample_adapter_preserves_supported_outputs(
    monkeypatch, relative_path, object_key, table_name, delimiter
):
    module, fake_job = _load_etl(
        monkeypatch,
        f"etl_bactopia_samples_{table_name.replace('-', '_')}_test",
        "assets/etl/etl_bactopia_samples.py",
        object_key,
        _read_fixture(relative_path),
    )

    key, rows = _written_csv(fake_job)
    parsed_rows = list(
        csv.reader(
            io.StringIO(_read_fixture(relative_path).decode()),
            delimiter=delimiter,
        )
    )

    assert module.SAMPLE_ADAPTER.__class__.__name__ == (
        "BactopiaOutputContractV1SampleAdapter"
    )
    assert key == (
        f"{table_name}/sample_id=sample/{Path(relative_path).stem}.csv"
    )
    assert rows == parsed_rows


def test_v4_sample_adapter_rejects_inconsistent_rows(monkeypatch):
    with pytest.raises(
        ValueError, match="Unexpected Bactopia output row width"
    ):
        _load_etl(
            monkeypatch,
            "etl_bactopia_samples_schema_test",
            "assets/etl/etl_bactopia_samples.py",
            "pipeline-output/bactopia-runs/run-1/sample/main/assembler/sample.tsv",
            b"contig\tlength\ncontig-1\t100\textra\n",
        )
