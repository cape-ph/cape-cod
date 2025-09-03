"""Module of compute abstractions."""

import os
import os.path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from abc import abstractmethod
from io import BytesIO

import pulumi_aws as aws
from pulumi import (
    FileArchive,
    FileAsset,
    Output,
    ResourceOptions,
    log,
)

from capeinfra.resources.objectstorage import (
    VersionedBucket,
)
from capepulumi import CapeComponentResource


class CapeLambdaLayer(CapeComponentResource):
    """CapeComponentResource wrapping a LambdaLayer.

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
    # resource name suffix for layer resources
    LAYER_RES_SUFFIX = "lyr"

    def __init__(
        self,
        name: str,
        objstore: VersionedBucket,
        *args,
        description: str | None = None,
        license_info: str | None = None,
        compatible_runtimes: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(
            self.type_name,
            name,
            *args,
            **kwargs,
        )
        self.layer_name = name
        self._lambda_layer = None
        self.layer_args = {
            "description": description,
            "license_info": license_info,
            "compatible_runtimes": compatible_runtimes,
        }
        self._objstore = objstore
        self._remote_zip_key = None
        self._layer_obj = None

        # see maybe_cleanup for note about this.
        self._cleanup_tmp = False

        # unfortunately, using tempfile.TemporaryDirectory context manager here
        # gets cleaned up too quickly unless everything goes perfect (debugging
        # with it is hard). the `delete` param to the constructor isn't
        # available in python 3.10, so we're using mkdtmp

        # our local layer assets will go here. THIS MUST BE CLEANED UP MANUALLY
        self._prefix_dir = tempfile.mkdtemp(
            prefix=f"{self.layer_name}-lambda-layer-"
        )
        self._local_zip_pth = os.path.join(self._prefix_dir, self.LAYER_ZNAME)

    @property
    def lambda_layer(self):
        """Accessor for the _lambda_layer member.

        Causes the layer to be created if it has not been already.

        Returns:
            The _lambda_layer member.
        """
        if self._lambda_layer is None:
            self._make_layer()
        return self._lambda_layer

    def should_deploy_local_layer(self):
        """Determine if the layer should be deployed or imported.

        The return of this method is a Pulumi Output wrapping a boolean.
        This method should be overridden when special logic warrants.

        Returns:
            A Pulumi Output wrapping a boolean stating if the local layer
            contents should be deployed (True) or if the remote contents should
            be imported (False).
        """
        return Output.all().apply(lambda _: True)

    def _make_layer(self):
        """Construct the layer we are wrapping."""
        self.prepare_local_layer_contents()
        deploy_local = self.should_deploy_local_layer()
        layer_assets = deploy_local.apply(
            lambda b: self.publish_layer_assets(b)
        )

        layer_archive = layer_assets[0]

        self._lambda_layer = aws.lambda_.LayerVersion(
            f"{self.layer_name}-lmbd-lyr",
            layer_name=self.layer_name,
            **self.layer_args,
            s3_bucket=layer_archive.bucket,
            s3_key=layer_archive.key,
            s3_object_version=layer_archive.version_id,
            opts=ResourceOptions(parent=self, depends_on=[layer_archive]),
        )

    def maybe_cleanup(self):
        """Cleanup tmp assets if configured for that."""
        # NOTE: This doesn't work as desired yet. Because so much of pulumi is
        #       async, we need to know that all things using these files are
        #       done before removing. For now we will not delete tmp files

        if self._cleanup_tmp:
            shutil.rmtree(self._prefix_dir)

    # TODO: this property should really go into CapeComponentResource. it's in
    #       use in the Swimlane hierarchy aids in inheritance. we would need to
    #       get all resources defining this and potentially require
    #       re-deployment of some resources, so it's not a simple fix.
    @property
    @abstractmethod
    def type_name(self) -> str:
        """Abstract property to get the type_name (pulumi namespacing)."""
        pass

    @property
    def remote_zip_key(self):
        """Return the remote zip key, setting default if not overridden."""
        if self._remote_zip_key is None:
            self._remote_zip_key = "/".join(
                [self.LAYERS_OBJST_PREFIX, self.layer_name, self.LAYER_ZNAME]
            )
        return self._remote_zip_key

    # TODO: this doesn't really fit here, but is needed. move it somewhere
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

        return True

    @abstractmethod
    def prepare_local_layer_contents(self):
        """Handle population of the local layer contents.

        This is always called, even if there is no change against a remote
        object.
        """
        pass

    def _publish_asset(self, asset, objkey, res_suffix, import_id=None):
        """Publish an archive to S3.

        If the import_id is not None, this doesn't actually result in anything
        new being "published" but references to remote objects are imported into
        pulumi's world so things are tracked correctly.

        Args:
            asset: The pulumi asset to publish.
            objkey: The object key for the archive in S3.
            res_suffix: The suffix for the pulumi managed resource name for the
                        published asset.
            import_id: If importing an existing remote resource, this is the
                       import id to use.
        Returns:
            The BucketObjectV2
        """
        # add new objects or get references for the existing ones so pulumi
        # manages correctly

        return self._objstore.add_object(
            f"{self.layer_name}-{res_suffix}",
            objkey,
            asset,
            import_id=import_id,
        )

    @abstractmethod
    def publish_layer_assets(self, deploy_local):
        """Publish assets for the layer.

        NOTE: This is called via an Output.apply lambda.


        Args:
            deploy_local: True if we are deploying the local layer contents,
                          False if import ids should be specified or pulumi
                          managed. Only needed to be False in very specific
                          circumstances (e.g. importing remote resources into
                          pulumi deployments).
        Returns:
            The list of published assets for the layer. The first item in the
            list *must* be the reference to the layer archive (needed by the
            LayerVersion constructor).
        """
        pass


class CapeGHReleaseLambdaLayer(CapeLambdaLayer):
    """CapeComponentResource wrapping a github release LambdaLayer.

    Args:
        name: The short name for the layer resource.
        uri: The github repository URI.
        tag: The release tag.
        asset: The asset in the tagged release that is the layer archive.
        objstore: The VersionedBucket where the layer zip and manifest will be
                  stored.
        description: An optional description for the layer resource.
        license_info: Optional license info for the layer. Matches the
                      form of the LambdaLayer arg of the same name.
        compatible_runtimes: Optional list of runtimes for the layer. Matches
                             the form of the LambdaLayer arg of the same name.
    """

    def __init__(
        self,
        name: str,
        uri: str,
        tag: str,
        asset: str,
        objstore: VersionedBucket,
        *args,
        **kwargs,
    ):
        super().__init__(
            name,
            objstore,
            *args,
            desc_name=(f"{name} pre-built GitHub release Lambda layer."),
            **kwargs,
        )

        self.uri = uri
        self.tag = tag
        self.asset = asset
        self._layer_archive_uri = None

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:resources:compute:CapeGHReleaseLambdaLayer"

    @property
    def layer_archive_uri(self):
        """Return the full release layer archive URI."""
        if self._layer_archive_uri is None:
            self._layer_archive_uri = (
                f"{self.uri}/releases/download/{self.tag}/{self.asset}"
            )
        return self._layer_archive_uri

    def prepare_local_layer_contents(self):
        """Handle population of the local layer contents."""
        # Fetch the remote archive and put it in the prefix directory.
        with (
            urllib.request.urlopen(self.layer_archive_uri) as resp,
            open(self._local_zip_pth, "wb") as zf,
        ):
            shutil.copyfileobj(resp, zf)

    def publish_layer_assets(self, deploy_local):
        """Publish assets for the layer.

        Args:
            deploy_local: True the local layer contents should be published,
                          False if references to remote objects should be
                          imported. Only needs to be False in very specific
                          circumstances (e.g. importing remote resources into
                          pulumi deployments).
        Returns:
            The list of published assets for the layer. The first item in the
            list *must* be the reference to the layer archive (needed by the
            LayerVersion constructor).
        """
        # because this type of layer is built from a remote managed (and
        # release-versioned) archive, we really should never have deploy_local
        # as False here. We will let the fact that we will not deploy the same
        # file (that has the same file hash) over an existing one due to how the
        # Pulumi aws.s3 BucketObjectv2 works.
        layer_obj = self._publish_asset(
            FileArchive(self._local_zip_pth),
            self.remote_zip_key,
            self.LAYER_RES_SUFFIX,
            import_id=None if deploy_local else self.remote_zip_key,
        )

        return [layer_obj]


class CapePythonLambdaLayer(CapeLambdaLayer):
    """CapeComponentResource wrapping a python LambdaLayer.

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
    """

    # local and remote filename for the layer manifest file
    MANIFEST_NAME = "manifest.txt"
    # suffix for manifest bucket object resources
    MANIFEST_RES_SUFFIX = "mnfst"

    def __init__(
        self,
        name: str,
        reqs: str,
        objstore: VersionedBucket,
        *args,
        **kwargs,
    ):
        super().__init__(
            name,
            objstore,
            *args,
            desc_name=f"{name} Python Lambda layer.",
            **kwargs,
        )

        self.reqs = reqs

        # in addition to a layer archive, this type of layer also stores a
        # manifest in s3
        self._remote_manifest_key = None

        self._local_manifest_pth = os.path.join(
            self._prefix_dir, self.MANIFEST_NAME
        )
        self._install_dir = os.path.join(self._prefix_dir, "python")

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:resources:compute:CapePythonLambdaLayer"

    @property
    def remote_manifest_key(self):
        """Return the remote manifest key, setting default if not overridden."""
        if self._remote_manifest_key is None:
            self._remote_manifest_key = "/".join(
                [self.LAYERS_OBJST_PREFIX, self.layer_name, self.MANIFEST_NAME]
            )
        return self._remote_manifest_key

    def prepare_local_layer_contents(self):
        """Install layer packages locally to a temporary directory."""

        # the full pip command we'll run
        pip_cmd = f"pip install -r {self.reqs} -t {self._install_dir}"
        pip_args = pip_cmd.split()
        if self._run_command(pip_args):
            return self._pip_list_layer()
        else:
            raise RuntimeError(
                f"Error preparing local layer contents for layer: "
                f"{self.layer_name}"
            )

    def _pip_list_layer(self):
        """Generate the pip list file for the local layer environment."""

        rc = True
        # the full pip command we'll run (in the format desired by
        # subprocess.run)
        pip_cmd = f"pip list --format freeze --path {self._install_dir}"
        pip_args = pip_cmd.split()
        with open(self._local_manifest_pth, "w") as manifest:
            rc = self._run_command(pip_args, outstream=manifest)
        return rc

    def should_deploy_local_layer(self):
        """Determine if the layer should be deployed or imported.

        The return of this method is a Pulumi Output wrapping a boolean.
        This method should be overridden when special logic warrants.

        Returns:
            A Pulumi Output wrapping a boolean stating if the local layer
            contents should be deployed (True) or if the remote contents should
            be imported (False).
        """
        deploy_local = Output.all().apply(lambda _: True)

        manifest_contents = self._objstore.get_object_contents(
            self.remote_manifest_key
        )

        # if manifest_contents is None, there was no remote manifest and we
        # have to deploy the local one.
        if manifest_contents is not None:
            deploy_local = manifest_contents.apply(
                lambda mc: not self._do_layers_match(
                    # NOTE: we already checked mc for None, but that doesn't
                    #       make checkers happy. doing the 'or b""' to get
                    #       around that
                    BytesIO(mc or b"")
                    .getvalue()
                    .decode("utf-8")
                )
            )

        return deploy_local

    def _do_layers_match(self, manifest_contents):
        """Return boolean stating if local and remote manifests match.

        Args:
            manifest_contents: The utf-8 contents of the remote manifest.

        Returns:
            True if the remote and local manifests match, else False.
        """
        layers_match = True

        if manifest_contents is not None:
            # we'll read both files into lists of lines then do set math to
            # determine if they're the same or not. This way only the contents
            # are diffed, nit the order.

            local_manifest_lines = open(
                self._local_manifest_pth, "r"
            ).readlines()

            # readlines keeps line endings, so make sure we do same here.
            remote_manifest_lines = manifest_contents.splitlines(keepends=True)

            # NOTE: difflib.Differ exists, but is not really what we want.
            #       making sure the set of lines is the same in both
            #       regardless of order is better than trying to determine what
            #       lines are different and which file has the defferences

            layers_match = set(local_manifest_lines) == set(
                remote_manifest_lines
            )

        return layers_match

    def publish_layer_assets(self, deploy_local):
        """Publish our layer assets to S3 or get references to existing ones.

        Args:
            deploy_local: True if the local layer contents should be deployed,
                          False if remote objects should be imported as
                          references.
        Returns:
            The list of published assets for the layer. The first item in the
            list *must* be the reference to the layer archive (needed by the
            LayerVersion constructor).
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

        # in all cases, the manifest contents will be this value. if the remote
        # and local manifests have the same contents, then our import will work
        # even if we give a new file. not so much in the case of the zips...

        manifest_obj = self._publish_asset(
            FileAsset(self._local_manifest_pth),
            self.remote_manifest_key,
            self.MANIFEST_RES_SUFFIX,
            import_id=None if deploy_local else self.remote_manifest_key,
        )

        def write_local_zip(contents):
            """Write a pulumi Output to a local file.

            This  file will be written to our local zip path.

            Args:
                contents: A pulumi Output containing the vytes to write to the
                          file.
            """
            with open(self._local_zip_pth, "wb") as zfile:
                zfile.write(contents)

        if deploy_local:
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

        else:
            # need to get the zipfile from s3 and then re-upload in the import
            # or pulumi will see a change...
            remote_zip_contents = self._objstore.get_object_contents(
                self.remote_zip_key
            )
            if remote_zip_contents is not None:
                # manifest was found in s3, so we need to compare it to local stuff
                # and publish if there are changes
                remote_zip_contents.apply(lambda rzc: write_local_zip(rzc))

        # the _local_zip_pth should now be usable regardless of if we imported
        # or have a new set of files.
        layer_obj = self._publish_asset(
            FileArchive(self._local_zip_pth),
            self.remote_zip_key,
            self.LAYER_RES_SUFFIX,
            import_id=None if deploy_local else self.remote_zip_key,
        )

        return [layer_obj, manifest_obj]
