"""Module of compute abstractions."""

import csv
import json
import tempfile
from typing import Any

import pulumi_aws as aws
from pulumi import FileArchive, FileAsset, Output, ResourceOptions, error, warn
from pulumi_command import local

import capeinfra
from capeinfra.iam import get_inline_role
from capeinfra.resources.objectstorage import VersionedBucket
from capeinfra.util.naming import disemvowel
from capepulumi import CapeComponentResource


class CapePythonLambdaLayer(CapeComponentResource):
    """CapeComponentResource wrapping a python LambdaLayer.

    One and only one of {code_zip_pth, reqs_pth} is required. A

    Args:
        name: The short name for the layer resource.
        description: An optional description for the layer resource.
        license_info: Optional license info for the layer. Matches the
                      form of the LambdaLayer arg of the same name.
        compatible_runtimes: Optional list of runtimes for the layer. Matches
                             the form of the LambdaLayer arg of the same name.

        code_zip_pth: Optional path to a zip file containing all the
                      dependencies to be added to the layer.
        reqs_pth: Optional path to a requirements file specifying the
                  dependincies to be added to the layer.
    Raises:
        ValueError: If neither or both of  {code_zip_pth, reqs_pth} is
        specified. Exactly one of these is required.
    """

    def __init__(
        self,
        name: str,
        description: str | None = None,
        license_info: str | None = None,
        compatible_runtimes: list[str] | None = None,
        code_zip_pth: str | None = None,
        reqs_pth: str | None = None,
        *args,
        **kwargs,
    ):
        if code_zip_pth is None and reqs_pth is None:
            msg = (
                f"Cannot specify a CapePyLambdaLayer without a code zip file "
                f"OR a requirements file. At least one is required (layer "
                f"name: {name})."
            )
            error(msg)
            raise ValueError(msg)

        if None not in (code_zip_pth, reqs_pth):
            msg = (
                f"Cannot specify a CapePyLambdaLayer with a code zip file "
                f"AND a requirements file. Only one may be specified (layer "
                f"name: {name})."
            )
            error(msg)
            raise ValueError(msg)

        super().__init__(
            "capeinfra:resources:CapeLambdaLayer", name, *args, **kwargs
        )

        self.name = name
        self._prepare_layer_code(code_zip_pth, reqs_pth)

        self.lambda_layer = aws.lambda_.LayerVersion(
            f"{self.name}-lmbd-lyr",
            layer_name=self.name,
            description=description,
            license_info=license_info,
            compatible_runtimes=compatible_runtimes,
            code=self._code,
            opts=ResourceOptions(parent=self),
        )

    def _prepare_layer_code(self, code_zip_pth, reqs_pth):
        """Prepare a FileArchive containing the dependencies specified.

        Only one of the two arguments should be provided. As This is called
        internally to the class this is ensured elsewhere.

        Args:
            code_zip_pth: Optional (local) path to a zip file containing
                          dependencies to be placed in the layer.
            reqs_pth: Optional (local) path to a requirements file containing
                      dependencies to be placed in the layer.
        """
        if code_zip_pth is not None:
            self._code = FileArchive(code_zip_pth)
        else:
            # TODO: handle some kind of pip failure
            prefix_dir = tempfile.mkdtemp()
            pip_exit_status = local.Command(
                f"{self.name}-lmbdlyr-cmd",
                create=f"pip install -r {reqs_pth} -t {prefix_dir}",
            )
            warn(
                f"CapePyLambdaLayer {self.name} pip exit status: "
                f"{pip_exit_status}"
            )
            self._code = FileArchive(prefix_dir)
