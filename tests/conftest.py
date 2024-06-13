import pulumi
import pytest


class PulumiMock(pulumi.runtime.Mocks):
    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        return args.name, args.inputs

    def call(self, args: pulumi.runtime.MockCallArgs):
        return {}, []


@pytest.fixture(autouse=True)
def config_init(scope="function"):
    pulumi.runtime.set_mocks(PulumiMock())
