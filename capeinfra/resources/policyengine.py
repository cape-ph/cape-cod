"""Module related to the deployment of Policy as Code engines."""

import csv
import json
import pathlib
from typing import Any

import pulumi_aws as aws
from pulumi import FileArchive, FileAsset, Output, ResourceOptions, error

import capeinfra
from capeinfra.resources.objectstorage import VersionedBucket
from capeinfra.util.file import unzip_to
from capeinfra.util.naming import disemvowel
from capeinfra.util.repo import get_github_release_artifact
from capepulumi import CapeComponentResource


class CapeAuthzPolicyEngine(CapeComponentResource):
    """Class that handles creation of a policy store, schema and policies.

    NOTE: At this time we expect all policy repo assets to be in github in a
          downloadable release zip file that can be referenced by URL in the
          following format:

          https://github.com/<org>/<repo>/releases/download/<version>/<asset>

          Where <org> is only needed for repos in an organization.

          This asset zip should contain schema and policy directories. The
          files in these directories should conform to Cedar JSON format.
    """

    @property
    def default_config(self) -> dict:
        """Implementation of abstract property `default_config`.

        The default config for this class links to the publicly available CAPE
        PaC repo.

        Returns:
            The default config dict for the authz policy engine.
        """
        return {
            "repo_url": "https://github.com/cape-ph/cape-cedar-pac",
            # NOTE: this repo does not have a `latest` version at present,
            #       so this must be set to a real version number
            "version": "2025.04.29",
            "artifact_name": "cape-cedar-pac.zip",
        }

    def __init__(self, **kwargs):
        self.name = "cape-authz-policy-engine"
        super().__init__(
            "capeinfra:pac:engine:CapeAuthzPolicyEngine",
            self.name,
            desc_name="Resources for user Authz via policy engine in the CAPE infrastructure",
            **kwargs,
        )

        # download the configured policy zip to /tmp
        pac_zip_path = get_github_release_artifact(**self.config)
        if pac_zip_path is None:

            # cfg_dict = {k: v for k, v in self.config.items()}
            error(
                f"Could not download the Authz Policy Engine repository. "
                f"Check the config values: {self.config}. Halting deployment."
            )

        # unzip it. behold its majesty
        unzip_to(pac_zip_path)

        # we should now have all the files in /tmp/asset_name_without_zip. let's
        # get an object that represents that
        self.pac_path = pathlib.Path(pac_zip_path).with_suffix("")

        # now set about deploying all the policy engine resources.
        self.create_policy_store()
        self.create_policy_schema()
        self.create_policies()

    def create_policy_store(self):
        """"""
        # TODO: If more doesn't get added here, there's no need for a method
        self.authz_policy_store = aws.verifiedpermissions.PolicyStore(
            f"{self.name}-{disemvowel('policystore')}",
            # TODO: MODE SHOULD BE STRICT ONCE EVERYTHING WORKS!
            validation_settings={"mode": "OFF"},
            opts=ResourceOptions(parent=self),
        )

    def create_policy_schema(self):
        """"""
        # TODO:
        # - pass in the stuff needed to make schema (file path).
        # - make schema

        # We expect there to be a single `.json` file in the schema directory.
        # So make sure that's the case. There can be other files, but only one
        # json file.
        # TODO: maybe have a way to pass in schema file name cause this isn't a
        #       great check

        # TODO: if this is kept, clean it up. DRY violate
        pac_schema_glob = list(self.pac_path.glob("schema"))
        if len(pac_schema_glob) != 1:
            error(
                f"Could not find schema directory in authz policy directory: "
                f"{self.pac_path}. Halting deployment."
            )
        json_glob = list(pac_schema_glob[0].glob("*.json"))

        if len(json_glob) != 1:
            error(
                f"Could not find schema in authz policy directory: "
                f"{pac_schema_glob[0]}. Expected one json file and found "
                f"{len(json_glob)}. Halting deployment."
            )
        json_schema = json_glob[0]

        with open(json_schema, "r") as json_file:
            json_str = json_file.read()
            self.pac_schema = aws.verifiedpermissions.Schema(
                f"{self.name}-{disemvowel('policyschema')}",
                policy_store_id=self.authz_policy_store.id,
                definition={"value": json_str},
            )

        pass

    def create_policies(self):
        """"""
        # TODO:
        # - pass in the stuff needed to make policies (file path).
        # - loop files make policies
        pass
