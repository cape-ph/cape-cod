import json
import os
from unittest.mock import patch

import pulumi
import pytest
import yaml


class PulumiMock(pulumi.runtime.Mocks):
    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        return args.name, args.inputs

    def call(self, args: pulumi.runtime.MockCallArgs):
        return {}, []


@pytest.fixture(scope="module")
def mock_namespace():
    return "cape-mock"


@pytest.fixture(scope="session", autouse=True)
def config_init():
    pulumi.runtime.set_mocks(PulumiMock())
    with open("Pulumi.cape-cod-dev.yaml", "r") as pulumi_config_file:
        pulumi_config = yaml.safe_load(pulumi_config_file)["config"]
        for key in pulumi_config:
            pulumi_config[key] = json.dumps(pulumi_config[key])
        with patch.dict(
            os.environ, dict(PULUMI_CONFIG=json.dumps(pulumi_config))
        ):
            yield


@pytest.fixture(scope="module")
def mock_meta(mock_namespace):
    from capeinfra.meta.capemeta import CapeMeta
    from capeinfra.resources.pulumi import CapeComponentResource

    meta = CapeMeta(f"{mock_namespace}-meta")
    CapeComponentResource.meta = meta
    return meta


@pytest.fixture(scope="module")
def mock_datalake(mock_namespace):
    from capeinfra.datalake.datalake import DatalakeHouse

    return DatalakeHouse(
        f"{mock_namespace}-datalakehouse",
    )
