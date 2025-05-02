"""Module related to the deployment of Policy as Code engines."""

import csv
import json
import pathlib
from typing import Any

import pulumi_aws as aws
from pulumi import FileArchive, FileAsset, Output, ResourceOptions, error

import capeinfra
from capeinfra.resources.objectstorage import VersionedBucket
from capeinfra.util.file import exists_else_error, unzip_to
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

    def create_policy_schema(self, file_name: str | None = None):
        """Create an aws AVP schema for an AVP policy store.

        Args:
            file_name: The (optional) name of the schema file. If not provided
                       this method will look for a single json file in the
                       schema directory.
        """
        schema_dir = self.pac_path / "schema"
        schema_file = file_name if file_name else "*.json"

        exists_else_error(
            schema_dir,
            (
                f"Could not find policy engine schema directory: "
                f"{schema_dir}. Halting deployment."
            ),
        )

        schema_glob = list(schema_dir.glob(schema_file))

        if len(schema_glob) != 1:
            msg = (
                f"Could not determine policy engine schema in directory: "
                f"{schema_dir}. Expected one json file and found "
                f"{len(schema_glob)} files. Halting deployment."
            )
            error(msg)
            raise ValueError(msg)

        json_schema = schema_glob[0]

        with open(json_schema, "r") as json_file:
            self.pac_schema = aws.verifiedpermissions.Schema(
                f"{self.name}-{disemvowel('policyschema')}",
                policy_store_id=self.authz_policy_store.id,
                definition={"value": json_file.read()},
            )

    def create_policies(self):
        """Create a aws AVP policies for an AVP policy store."""
        policy_dir = self.pac_path / "policy"
        policy_files = "*.json"

        exists_else_error(
            policy_dir,
            (
                f"Could not find policy engine policy directory: "
                f"{policy_dir}. Halting deployment."
            ),
        )

        policy_glob = list(policy_dir.glob(policy_files))

        if not policy_glob:
            msg = (
                f"Could not find any policy engine policies in directory: "
                f"{policy_dir}. Halting deployment."
            )
            error(msg)
            raise ValueError(msg)

        for idx, p in enumerate(policy_glob):
            with open(p, "r") as json_policy:
                aws.verifiedpermissions.Policy(
                    # TODO: index policy names are bad. and change in
                    #       alphabetizing of input files would cause redos
                    #       of indices for no reason. Using some disemvowelled
                    #       filename might work, but naming limits...
                    f"{self.name}-plcy{idx}",
                    policy_store_id=self.authz_policy_store.id,
                    definition={
                        "static": {
                            "statement": json_policy.read(),
                            "description": f"Policy from file {p}",
                        },
                    },
                )
