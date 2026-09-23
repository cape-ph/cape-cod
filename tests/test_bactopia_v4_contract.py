"""Contract tests for the Bactopia v4.1 DAP and Batch submission wiring."""

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name, relative_path):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_submit_handler(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    return _load_module(
        "submit_dap_run_contract_test",
        "assets/api/capi/handlers/submit_dap_run.py",
    )


def _load_profile(name):
    path = REPO_ROOT / "assets" / "analysis-pipelines" / "bactopia" / name
    return json.loads(path.read_text())


def test_bactopia_v4_base_profile_uses_shared_runtime():
    profile = _load_profile("bactopia-base-4.1.0.json")
    schema = profile["parametersSchema"]

    assert profile["project"] == "bactopia/bactopia"
    assert profile["version"] == "v4.1.0"
    assert profile["execution"] == {"class": "general-analysis"}
    assert schema["properties"]["-profile"] == {
        "const": "docker",
        "default": "docker",
        "description": (
            "Use the Docker profile. AWS Batch execution comes from the "
            "CAPE-generated Nextflow runtime configuration."
        ),
    }
    assert "--aws_volumes" not in schema["properties"]
    assert profile["submission"] == {
        "optionsFieldName": "nextflowOptions",
        "encoding": "cli-string",
    }


def test_taxprofiler_kraken2_profile_has_runtime_policy():
    profile = _load_profile("taxprofiler-kraken2-2.0.1.json")
    override = profile["execution"]["nextflow"]["processOverrides"]["kraken2"]

    assert profile["project"] == "nf-core/taxprofiler"
    assert profile["version"] == "2.0.1"
    assert profile["execution"]["class"] == "taxonomic-profiling"
    assert override == {
        "selector": ".*KRAKEN2_KRAKEN2.*",
        "cpus": 2,
        "memory": "9.GB",
        "time": "4.h",
    }


def test_bactopia_v4_ont_profile_contract():
    profile = _load_profile("ont-bactopia-4.1.0.json")
    schema = profile["parametersSchema"]
    properties = schema["properties"]

    assert profile["inherits"] == ["bactopia-base-4.1.0"]
    assert schema["allOf"] == [{"$ref": "#/$defs/bactopia-base-4.1.0"}]
    assert properties["--skip_qc_plots"]["type"] == "boolean"
    assert properties["--skip_qc_plots"]["default"] is True
    assert {"--sample", "--ont", "--outdir"} <= set(schema["required"])
    assert "--skip_qc_plots" in {
        element["scope"].rsplit("/", 1)[-1]
        for element in profile["uiSchema"]["elements"]
    }


def test_v3_profiles_remain_available():
    for name in (
        "bactopia-base-3.2.0.json",
        "ont-bactopia-3.2.0.json",
    ):
        assert (
            REPO_ROOT / "assets" / "analysis-pipelines" / "bactopia" / name
        ).exists()


def test_submit_handler_reads_deployment_batch_values(monkeypatch):
    submit_handler = _load_submit_handler(monkeypatch)
    values = {
        "WORKFLOW_QUEUE_NAME": "workflow-queue",
        "NEXTFLOW_JOB_DEFINITION_NAME": "nextflow-job-definition",
        "JOB_QUEUE_NAME": "analysis-queue",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    assert submit_handler._get_batch_configuration() == {
        **values,
        "EXECUTION_CLASS_QUEUE_MAP": {},
    }


def test_submit_handler_rejects_missing_deployment_batch_values(monkeypatch):
    submit_handler = _load_submit_handler(monkeypatch)
    for name in (
        "WORKFLOW_QUEUE_NAME",
        "NEXTFLOW_JOB_DEFINITION_NAME",
        "JOB_QUEUE_NAME",
    ):
        monkeypatch.delenv(name, raising=False)

    assert submit_handler._get_batch_configuration() is None


def test_submit_handler_passes_profile_process_overrides(monkeypatch):
    submit_handler = _load_submit_handler(monkeypatch)
    for name, value in {
        "WORKFLOW_QUEUE_NAME": "workflow-queue",
        "NEXTFLOW_JOB_DEFINITION_NAME": "nextflow-job-definition",
        "JOB_QUEUE_NAME": "analysis-queue",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(
        "EXECUTION_CLASS_QUEUE_MAP",
        json.dumps({"taxonomic-profiling": "taxonomy-queue"}),
    )

    class FakePipelineTable:
        def get_pipelines_by_name(self, pipeline_name, pipeline_version):
            assert pipeline_name == "Taxprofiler Kraken2"
            assert pipeline_version == "2.0.1"
            return [
                {
                    "profile": {
                        "project": "nf-core/taxprofiler",
                        "version": "2.0.1",
                        "execution": {
                            "class": "taxonomic-profiling",
                            "nextflow": {
                                "processOverrides": {
                                    "kraken2": {
                                        "selector": ".*KRAKEN2_KRAKEN2.*",
                                        "cpus": Decimal("2"),
                                        "memory": "9.GB",
                                        "time": "4.h",
                                    }
                                }
                            },
                        },
                    }
                }
            ]

    monkeypatch.setattr(submit_handler, "PipelineTable", FakePipelineTable)
    captured = {}

    class FakeBatchClient:
        def submit_job(self, **kwargs):
            captured.update(kwargs)
            return {
                "jobArn": "arn:aws:batch:job/test",
                "jobName": "nextflow-test",
                "jobId": "job-test",
            }

    monkeypatch.setattr(submit_handler, "batch_client", FakeBatchClient())
    response = submit_handler.index_handler(
        {
            "body": json.dumps(
                {
                    "pipelineName": "Taxprofiler Kraken2",
                    "pipelineVersion": "2.0.1",
                    "nextflowOptions": "--run_kraken2",
                }
            )
        },
        SimpleNamespace(aws_request_id="request-test"),
    )

    assert response["statusCode"] == 200
    environment = {
        item["name"]: item["value"]
        for item in captured["containerOverrides"]["environment"]
    }
    assert environment["PIPELINE"] == "nf-core/taxprofiler"
    assert environment["PIPELINE_QUEUE"] == "taxonomy-queue"
    assert (
        json.loads(environment["NEXTFLOW_PROCESS_OVERRIDES"])["kraken2"]["cpus"]
        == 2
    )


def test_submit_handler_rejects_unknown_execution_class(monkeypatch):
    submit_handler = _load_submit_handler(monkeypatch)
    for name, value in {
        "WORKFLOW_QUEUE_NAME": "workflow-queue",
        "NEXTFLOW_JOB_DEFINITION_NAME": "nextflow-job-definition",
        "JOB_QUEUE_NAME": "analysis-queue",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(
        "EXECUTION_CLASS_QUEUE_MAP",
        json.dumps({"taxonomic-profiling": "taxonomy-queue"}),
    )

    class FakePipelineTable:
        def get_pipelines_by_name(self, pipeline_name, pipeline_version):
            return [
                {
                    "profile": {
                        "project": "example/pipeline",
                        "version": pipeline_version,
                        "execution": {"class": "unsupported-class"},
                    }
                }
            ]

    monkeypatch.setattr(submit_handler, "PipelineTable", FakePipelineTable)
    submitted = False

    class FakeBatchClient:
        def submit_job(self, **kwargs):
            nonlocal submitted
            submitted = True
            return {}

    monkeypatch.setattr(submit_handler, "batch_client", FakeBatchClient())
    response = submit_handler.index_handler(
        {
            "body": json.dumps(
                {
                    "pipelineName": "Unknown",
                    "pipelineVersion": "1.0.0",
                    "nextflowOptions": "",
                }
            )
        },
        SimpleNamespace(aws_request_id="request-test"),
    )

    assert response["statusCode"] == 400
    assert submitted is False


def test_submit_handler_uses_deployment_batch_values(monkeypatch):
    submit_handler = _load_submit_handler(monkeypatch)
    monkeypatch.setenv("WORKFLOW_QUEUE_NAME", "workflow-queue")
    monkeypatch.setenv(
        "NEXTFLOW_JOB_DEFINITION_NAME", "nextflow-job-definition"
    )
    monkeypatch.setenv("JOB_QUEUE_NAME", "analysis-queue")

    captured = {}

    class FakeBatchClient:
        def submit_job(self, **kwargs):
            captured.update(kwargs)
            return {
                "jobArn": "arn:aws:batch:job/test",
                "jobName": "nextflow-test",
                "jobId": "job-test",
            }

    monkeypatch.setattr(submit_handler, "batch_client", FakeBatchClient())
    event = {
        "body": json.dumps(
            {
                "pipelineProject": "bactopia/bactopia",
                "pipelineVersion": "v4.1.0",
                "nextflowOptions": "-profile docker",
            }
        )
    }

    response = submit_handler.index_handler(
        event, SimpleNamespace(aws_request_id="request-test")
    )

    assert response["statusCode"] == 200
    assert captured["jobQueue"] == "workflow-queue"
    assert captured["jobDefinition"] == "nextflow-job-definition"
    environment = {
        item["name"]: item["value"]
        for item in captured["containerOverrides"]["environment"]
    }
    assert environment["PIPELINE_QUEUE"] == "analysis-queue"


def test_kickstart_renders_structured_process_overrides():
    entrypoint = (
        REPO_ROOT / "assets/containers/nextflow-kickstart/entrypoint.sh"
    ).read_text()

    assert (
        "NEXTFLOW_PROCESS_OVERRIDES=${NEXTFLOW_PROCESS_OVERRIDES}" in entrypoint
    )
    assert "Invalid validated Nextflow process override policy" in entrypoint
    assert "to_entries[]" in entrypoint
    assert "withName: '${selector}'" in entrypoint


def _find_mapping_with_id(value, target_id):
    if isinstance(value, dict):
        if value.get("id") == target_id:
            return value
        for child in value.values():
            result = _find_mapping_with_id(child, target_id)
            if result is not None:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _find_mapping_with_id(child, target_id)
            if result is not None:
                return result
    return None


def test_dev_api_scopes_dynamic_batch_values_to_submit_handler():
    pulumi_config = yaml.safe_load(
        (REPO_ROOT / "Pulumi.cape-cod-dev.yaml").read_text()
    )
    submit_handler = _find_mapping_with_id(
        pulumi_config, "submit_dap_run_handler"
    )

    assert submit_handler is not None
    assert set(submit_handler["env_vars"]) == {
        "WORKFLOW_QUEUE_NAME",
        "NEXTFLOW_JOB_DEFINITION_NAME",
        "JOB_QUEUE_NAME",
        "EXECUTION_CLASS_QUEUE_MAP",
    }


def test_dev_config_routes_taxonomic_runs_to_general_analysis():
    pulumi_config = yaml.safe_load(
        (REPO_ROOT / "Pulumi.cape-cod-dev.yaml").read_text()
    )
    private_config = pulumi_config["config"]["cape-cod:swimlanes"]["private"]
    compute = private_config["compute"]
    environments = {
        (item["name"], item.get("generation")): item
        for item in compute["environments"]["batch"]
    }

    assert compute["execution_routes"] == {
        "workflow-orchestration": {
            "environment": "workflows",
            "generation": 1,
        },
        "general-analysis": {
            "environment": "analysis",
            "generation": 1,
        },
        "taxonomic-profiling": {
            "environment": "analysis",
            "generation": 1,
        },
    }
    assert environments[("workflows", 1)]["image"] == "ami-0ad4ff177982b3e5e"
    assert environments[("analysis", 1)]["image"] == "ami-0ad4ff177982b3e5e"
    assert not any(
        item["name"] == "taxonomic-profiling"
        for item in compute["environments"]["batch"]
    )


def test_kickstart_separates_parent_and_batch_host_cli_paths():
    entrypoint = (
        REPO_ROOT / "assets/containers/nextflow-kickstart/entrypoint.sh"
    ).read_text()

    assert "PARENT_AWS_CLI_PATH=$(command -v aws)" in entrypoint
    assert (
        "NEXTFLOW_AWS_BATCH_CLI_PATH=${NEXTFLOW_AWS_BATCH_CLI_PATH}"
        in entrypoint
    )
    assert "cliPath = '${NEXTFLOW_AWS_BATCH_CLI_PATH}'" in entrypoint
    assert "cliPath = '${PARENT_AWS_CLI_PATH}'" not in entrypoint


def _find_nextflow_job(value):
    if isinstance(value, dict):
        if value.get("image") == "nextflow_kickstart" and value.get(
            "command"
        ) == ["/usr/local/bin/entrypoint.sh"]:
            return value
        for child in value.values():
            result = _find_nextflow_job(child)
            if result is not None:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _find_nextflow_job(child)
            if result is not None:
                return result
    return None


def test_dev_nextflow_job_passes_batch_host_cli_path():
    pulumi_config = yaml.safe_load(
        (REPO_ROOT / "Pulumi.cape-cod-dev.yaml").read_text()
    )
    nextflow_job = _find_nextflow_job(pulumi_config)

    assert nextflow_job is not None
    assert {
        item["name"]: item["value"] for item in nextflow_job["environment"]
    }["NEXTFLOW_AWS_BATCH_CLI_PATH"] == "/home/ec2-user/miniconda/bin/aws"
