"""Module of compute abstractions."""

import os
import os.path
import subprocess
import tempfile
import zipfile
from io import BytesIO

import pulumi_aws as aws
from pulumi import (
    FileArchive,
    FileAsset,
    ResourceOptions,
    log,
)

from capeinfra.resources.objectstorage import (
    VersionedBucket,
)
from capepulumi import CapeComponentResource


class CapePythonLambdaLayer(CapeComponentResource):
    """CapeComponentResource wrapping a python LambdaLayer.

    One and only one of {code_zip_pth, reqs_pth} is required. A

    Args:
        name: The short name for the layer resource.
        reqs: The path to the requirements file for the layer.
        objstore: The VersionedBucket where the layer zip and manifest will be
                  stored.
        description: An optional description for the layer resource.
        license_info: Optional license info for the layer. Matches the
                      form of the LambdaLayer arg of the same name.
        compatible_runtimes: Optional list of runtimes for the layer. Matches
                             the form of the LambdaLayer arg of the same name.
    Raises:
        ValueError: If neither or both of  {code_zip_pth, reqs_pth} is
        specified. Exactly one of these is required.
    """

    # prefix for all layers in object storage
    LAYERS_OBJST_PREFIX = "layers"
    # local and remote filename for the layer zip file
    LAYER_ZNAME = "layer.zip"
    # local and remote filename for the layer manifest file
    MANIFEST_NAME = "manifest.txt"

    def __init__(
        self,
        name: str,
        reqs: str,
        objstore: VersionedBucket,
        description: str | None = None,
        license_info: str | None = None,
        compatible_runtimes: list[str] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            "capeinfra:resources:compute:CapePythonLambdaLayer",
            name,
            desc_name="Abstraction of a config-driven Python Lambda layer",
            **kwargs,
        )
        self.layer_name = name
        self.reqs = reqs
        self._objstore = objstore
        self._remote_manifest_key = None
        self._remote_zip_key = None
        self._layer_obj = None
        self._manifest_obj = None

        # unfortunately, using tempfile.TemporaryDirectory context manager here
        # gets cleaned up too quickly unless everything goes perfect (debugging
        # with it is hard). the `delete` param to the constructor isn't
        # available in python 3.10, so we're using mkdtmp

        self._prefix_dir = tempfile.mkdtemp(
            prefix=f"{self.layer_name}-lambda-layer-"
        )

        self._local_manifest_pth = os.path.join(
            self._prefix_dir, self.MANIFEST_NAME
        )
        self._local_zip_pth = os.path.join(self._prefix_dir, self.LAYER_ZNAME)
        self._install_dir = os.path.join(self._prefix_dir, "python")

        # we will do this in all cases, even if there is no difference against
        # the remote (because we won't know there are no differences without
        # doing this)
        self.build_local_layer()
        self.pip_list_layer()

        manifest_contents = self._objstore.get_object_contents(
            self.remote_manifest_key
        )
        if manifest_contents is not None:
            # manifest was found in s3, so we need to compare it to local stuff
            # and publish if there are changes
            manifest_contents.apply(lambda mc: self.handle_manifest_output(mc))
        else:
            # manifest was not found in s3, so blindly publish what we have
            self.publish_layer_assets()

        # by here we have everything we need to make the layer object
        self.lambda_layer = aws.lambda_.LayerVersion(
            f"{self.layer_name}-lmbd-lyr",
            layer_name=self.layer_name,
            description=description,
            license_info=license_info,
            compatible_runtimes=compatible_runtimes,
            s3_bucket=self._objstore.bucket.id.apply(lambda b: f"{b}"),
            # s3_key=self._layer_obj_key,
            s3_key=self.remote_zip_key,
            opts=ResourceOptions(parent=self),
        )

        # TODO: maybe make this configurable? if everything goes well, delete
        #       the tempdir, but until we do that we'll need manual cleanup.
        # shutil.rmtree(self._prefix_dir)

    @property
    def remote_manifest_key(self):
        """Return the remote manifest key, setting default if not overridden."""
        if self._remote_manifest_key is None:
            self._remote_manifest_key = (
                f"{self.LAYERS_OBJST_PREFIX}/{self.layer_name}"
                f"/{self.MANIFEST_NAME}"
            )
        return self._remote_manifest_key

    @property
    def remote_zip_key(self):
        """Return the remote zip key, setting default if not overridden."""
        if self._remote_zip_key is None:
            self._remote_zip_key = (
                f"{self.LAYERS_OBJST_PREFIX}/{self.layer_name}"
                f"/{self.LAYER_ZNAME}"
            )
        return self._remote_zip_key

    def _run_command(self, cmd_args, outstream=None, errstream=None):
        """Run a shell command as a subprocess and raise error on failure.

        Args:
            cmd_args: A list of tokens for the command. Each space separated
                      token should be a list element.
            outstream: Optional file-like for the output stream of the command.
                       Defaults to None, which will go to pulumi standard out.
            errstream: Optional file-like for the error stream of the command.
                       Defaults to None, which will go to pulumi standard out.
        """
        cp = subprocess.run(
            cmd_args,
            stdout=outstream,
            stderr=errstream,
        )

        # if there's an error running the command, log it and bail.
        if cp.returncode != 0:
            msg = f"Lambda layer command failed. error: {cp.stderr}"
            log.error(msg)
            raise RuntimeError(msg)

    def build_local_layer(self):
        """Install layer packages locally to a temporary directory."""

        # the full pip command we'll run (in the format desired by
        # subprocess.run)
        pip_args = f"pip install -r {self.reqs} -t {self._install_dir}".split()
        self._run_command(pip_args)

    def pip_list_layer(self):
        """Generate the pip list file for the local layer environment."""

        # the full pip command we'll run (in the format desired by
        # subprocess.run)
        pip_args = (
            f"pip list --format freeze --path {self._install_dir}".split()
        )
        with open(self._local_manifest_pth, "w") as manifest:
            self._run_command(pip_args, outstream=manifest)

    def handle_manifest_output(self, manifest_contents):
        """Handle remote manifest based on (mis-)match with local manifest.

        Args:
            manifest_contents: A pulumi Output linked to the contents of the
                               remote manifest for the layer.
        """
        obj_env_spec = BytesIO(manifest_contents)

        # check if the manifests match or have differences. We'll import if
        # there are no differences otherwise we'll publish new ones
        import_objs = not self.layers_have_diffs(obj_env_spec)

        self.publish_layer_assets(import_objs=import_objs)

    def layers_have_diffs(self, env_spec):
        """Return boolean stating if local and remote manifests have differences.

        Args:
            env_spec: A BytesIO containing the contents of the remote manifest.

        Returns:
            True if the remote and local manifests match, else False.
        """
        diffs = True

        if env_spec is not None:
            # we'll read both files into lists of lines then do set math to
            # determine if they're the same or not. This way only the contents
            # are diffed, nit the order.

            local_manifest_lines = open(
                self._local_manifest_pth, "r"
            ).readlines()

            # readlines keeps line endings, so make sure we do same here.
            remote_manifest_lines = (
                env_spec.getvalue().decode("utf-8").splitlines(keepends=True)
            )

            # NOTE: difflib.Differ exists, but is not really what we want.
            #       making sure the set of lines is the same in both
            #       regardless of order is better than trying to determine what
            #       lines are different and which file has the defferences
            diffs = (
                True
                if set.difference(
                    set(local_manifest_lines), set(remote_manifest_lines)
                )
                else False
            )
        return diffs

    def publish_layer_assets(self, import_objs=False):
        """Publish our layer assets to S3 or get references to existing ones.

        Args:
            import_objs: True if the remote objects should be imported as
                         references, False if we are publishing new files.
        """

        # NOTE: Apologies to anyone that comes here later. I regret some
        #       things...
        #       Lambda wants "deployment packages" which are zip files in this
        #       case. Problem with zip files is that creating the same one 2x
        #       will yield different files (timestamps and such). Uploading
        #       these different files to s3 is (rightfully) seen as a new file
        #       version, so pulumi shows differences in multiple places.
        #       The way pulumi works, it wants to know about every resource it
        #       manages. So it is not possible to say "add this zip file to s3
        #       if it has changed, but don't do anything if it hasn't". Because
        #       doing nothing with that file is seen by pulumi as it being
        #       deleted from the deployment. So we need a mechanism to import an
        #       existing ref. Pulumi has a way to do this, but you have to "add"
        #       the exact same object (constructing a BucketObjectV2 with all
        #       the same params as when you add, but give it an import id that
        #       matches what a new object would have been given). With a zip
        #       file, this means we need to pass the same zip file to the
        #       add_object call. But that zip file is in s3 and we can't
        #       recreate locally...see where this is going?
        #       So "publish" here is not just uploading a new version of a zip.
        #       It can mean that if the manifests match we need to download the
        #       current zip out of s3 and then re-add it with an import id.
        #       WE NEED TO SERIOUSLY LOOK AT A BETTER WAY TO DO THIS.

        # in all cases, the manifest conetents will be this value. if the remote
        # and local manifests have the same cotents, then our import will work
        # even if we give a new file. not so much in the case of the zips...
        manifest = FileAsset(self._local_manifest_pth)
        code = None

        def write_local_zip(contents):
            """Write a pulumi Output to a local file.

            This  file will be written to our local zip path.

            Args:
                contents: A pulumi Output containing the vytes to write to the
                          file.
            """
            with open(self._local_zip_pth, "wb") as zfile:
                zfile.write(contents)

        if import_objs:
            # need to get the zipfile from s3 and then re-upload in the import
            # or pulumi will see a change...
            remote_zip_contents = self._objstore.get_object_contents(
                self.remote_zip_key
            )
            if remote_zip_contents is not None:
                # manifest was found in s3, so we need to compare it to local stuff
                # and publish if there are changes
                remote_zip_contents.apply(lambda rzc: write_local_zip(rzc))
        else:
            # first, build up the zip file for as lambda will expect it. the format
            # of this archive is very important. it must contain a single directory
            # named `python` that then contains all of the dependencies in a manner
            # consistent with a pip installation.
            # we installed our requirements above into just such a directory,
            # and so need to zip only the python directory (ignoring all other
            # pathing).
            with zipfile.ZipFile(
                self._local_zip_pth, "w", zipfile.ZIP_DEFLATED
            ) as zp:
                # 2nd tuple item is a list of dirs, which we ignore
                for root, _, files in os.walk(self._install_dir):
                    for file in files:
                        zp.write(
                            os.path.join(root, file),
                            # remove existing full pathing in the zip and make
                            # relative to the python directory
                            arcname=os.path.join(
                                root.replace(f"{self._prefix_dir}/", ""), file
                            ),
                        )

        # the _local_zip_pth should now be usable regardless of if we imported
        # or have a new set of files.
        code = FileArchive(self._local_zip_pth)

        # add new objects or get references for the existing ones so pulumi
        # manages correctly
        self._layer_obj = self._objstore.add_object(
            f"{self.layer_name}-lyr",
            self.remote_zip_key,
            code,
            import_id=self.remote_zip_key if import_objs else None,
        )

        self._manifest_obj = self._objstore.add_object(
            f"{self.layer_name}-mnfst",
            self.remote_manifest_key,
            manifest,
            import_id=self.remote_manifest_key if import_objs else None,
        )
