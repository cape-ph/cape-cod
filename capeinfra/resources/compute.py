"""Module of compute abstractions."""

import csv
import json
import os
import os.path
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import pulumi_aws as aws
from pulumi import (
    AssetArchive,
    FileArchive,
    FileAsset,
    Output,
    ResourceOptions,
    error,
    warn,
)
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
        self._code = None

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

        Only one of the two arguments should be provided. As this method is
        called internally to the class argument consistency is ensured
        elsewhere.

        The zip file and directory of installed pip dependencies created by this
        method are not cleaned up. This is an artifact of testing and debugging
        this function that proved useful in practice. Be aware of this and if
        you need to ensure a layer is completely rebuilt (including pulling the
        packes), it is best to remove directories created by this function
        before performing a deployment (assuming the directories have not been
        purged another way as they are created in the system `tmp` directory.

        Args:
            code_zip_pth: Optional (local) path to a zip file containing
                          dependencies to be placed in the layer.
            reqs_pth: Optional (local) path to a requirements file containing
                      dependencies to be placed in the layer.
        """

        # NOTE: This function was attempted using pulumi's `local.Command`
        #       provider before this implementation. It seemed ok, but then
        #       suddenly stopped responding to changes that should have caused a
        #       rebuild of the layer (or that i thought should). also it
        #       appeared that there were some timing issues that sometimes had
        #       the zip file totally empty (as though it were being used prior
        #       to being finalized). Rather than wasting a ton of time, this was
        #       changed to a more direct implementation. The promise of
        #       `local.Command` is pretty useful, so when time permits we should
        #       look into making use of that and seeing if we can determine the
        #       issue(s) and how to solve them.

        if code_zip_pth is not None:
            # if we were handed a zip path, we can just use it as is
            self._code = FileArchive(code_zip_pth)
        else:
            # in this case we have a requirements file. we'll need to make a
            # local installation of all the packages and then zip those
            # appropriately. For AWS Lambda layers, this means we have a zip
            # containing a single `python/` directory into which all the
            # dependencies we need have been installed

            # name for the temp directory we will use to build our on-disk pip
            # installations
            layer_dir_name = f"{self.name}-lambda-layer"
            # name of the zip file we'll pass onto the lambday layer
            zip_name = f"{layer_dir_name}.zip"
            # full path to the directory we'll build our pip installations in
            prefix_dir = os.path.join(tempfile.gettempdir(), layer_dir_name)
            # `python` directoy required by AWS lambda. all pip dependencies
            # will go in here (via `pip install -t`)
            install_dir = os.path.join(prefix_dir, "python")

            # ensure our install direcrtory exists.
            # NOTE: making a tempdir here instead of a named directory gets
            #       cleaned up too fast. So we'll make a directory in the temp
            #       location and leave it there.
            # TODO: this may no longer be the case with move away from
            #       local.Command. re-examine
            Path(install_dir).mkdir(parents=True, exist_ok=True)

            # the full pip command we'll run (in the format desired by
            # subprocess.run)
            pip_args = [
                "pip",
                "install",
                "-r",
                f"{reqs_pth}",
                "-t",
                f"{install_dir}",
            ]

            # run the pip command. when completed, cp will contain all the
            # return values and output for the completed process
            cp = subprocess.run(
                pip_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            # if there's an error running pip, log it and bail.
            if cp.returncode != 0:
                msg = (
                    f"Lambda layer pip installation failed. error: {cp.stderr}"
                )
                error(msg)
                raise RuntimeError(msg)

            # build up the zip file for passing on to lambda. the format of this
            # archive is very important. iot must contain a single directory
            # called `python` that then contains all of the dependencies in a
            # manner consistent with a pip installation.
            # we installed our requirements above into just such a directory,
            # and so need to zip only the python directory (ignoring all other
            # pathing).
            # NOTE: this could be done with the system `zip` utility as well,
            #       though removing pathing is not so straight forward there
            #       (without changing directories. This is a bit more verbose,
            #       but also predictable
            with zipfile.ZipFile(
                f"{prefix_dir}/{zip_name}", "w", zipfile.ZIP_DEFLATED
            ) as zp:
                for root, dirs, files in os.walk(install_dir):
                    for file in files:
                        zp.write(
                            os.path.join(root, file),
                            arcname=os.path.join(
                                root.replace(f"{prefix_dir}/", ""), file
                            ),
                        )
            self._code = FileArchive(f"{prefix_dir}/{zip_name}")
