"""Contains resources used by the whole CAPE infra deployment."""

import csv
from typing import Any

import pulumi_aws as aws
from pulumi import FileArchive, FileAsset, Output, ResourceOptions

import capeinfra
from capeinfra.resources.objectstorage import VersionedBucket
from capepulumi import CapeComponentResource


class CapeMeta(CapeComponentResource):
    """Contains resources needed by all parts of the infra."""

    def __init__(self, name, **kwargs):
        # This maintains parental relationships within the pulumi stack
        super().__init__(
            "capeinfra:meta:capemeta:CapeMeta",
            name,
            config="meta",
            **kwargs,
        )
        self.automation_assets_bucket = VersionedBucket(
            f"{name}-assets-vbkt",
            desc_name=f"{self.desc_name} automation assets",
            opts=ResourceOptions(parent=self),
        )

        for etl_def in self.config.get("glue", "etl", default=[]):
            self.automation_assets_bucket.add_object(
                etl_def["name"],
                key=etl_def["key"],
                # NOTE: These should always be file assets in the ETL case
                #       (as opposed to archive assets)
                source=FileAsset(etl_def["srcpth"]),
            )

        self.capepy = CapePy(self.automation_assets_bucket)
        self.users = CapePrincipals(
            config=self.config.get("principals", default={})
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs(
            {
                "cape-meta-automation-assets-bucket": self.automation_assets_bucket.bucket
            }
        )


class CapePy(CapeComponentResource):
    def __init__(self, assets_bucket: VersionedBucket, **kwargs):
        self.name = "capepy"
        super().__init__(
            "capeinfra:meta:capemeta:CapePy",
            self.name,
            desc_name="Resources for distributing the CapePy library",
            **kwargs,
        )

        self.bucket = assets_bucket
        capepy_whl = "capepy-2.0.0-py3-none-any.whl"
        self.object = self.bucket.add_object(
            f"{self.name}-object",
            key=capepy_whl,
            source=FileAsset(f"./assets/capepy/{capepy_whl}"),
        )

        self.uri = Output.all(
            bucket=self.bucket.bucket.bucket, key=self.object.key
        ).apply(lambda args: f"s3://{args['bucket']}/{args['key']}")

        self.lambda_layer = aws.lambda_.LayerVersion(
            f"{self.name}-lmbd-lyr",
            layer_name=self.name,
            description="This layer provides the capepy Python library",
            license_info=" Apache-2.0",
            compatible_runtimes=["python3.10"],
            code=FileArchive("./assets/capepy/capepy_layer.zip"),
            opts=ResourceOptions(parent=self),
        )


class CapePrincipals(CapeComponentResource):
    """Class that handles config-based local user and group creation/association."""

    @property
    def default_config(self) -> dict:
        """Implementation of abstract property `default_config`.

        The default user/group config only contains an Admins group and a
        default local admin user.

        Returns:
            The default config dict for the user/group config
        """
        return {
            "groups": {
                "Admins": {
                    "description": "CAPE administrators group.",
                    "precedence": 1,
                }
            },
            "users": [
                {
                    "email": "cape.admin@example.com",
                    "temporary_password": "1CapeCodUser!",
                    "groups": ["Admins"],
                }
            ],
        }

    def __init__(self, **kwargs):
        self.name = "cape-principals"
        super().__init__(
            "capeinfra:meta:capemeta:CapePrincipals",
            self.name,
            desc_name="Resources for user management in the CAPE infrastructure",
            **kwargs,
        )

        self.user_pool = aws.cognito.UserPool(
            "cape-users",
            name="cape-users",
            account_recovery_setting={
                "recovery_mechanisms": [
                    {"name": "verified_email", "priority": 1}
                ]
            },
            admin_create_user_config={"allow_admin_create_user_only": True},
            password_policy={
                "minimum_length": 8,
                "require_lowercase": True,
                "require_numbers": True,
                "require_symbols": True,
                "require_uppercase": True,
                "temporary_password_validity_days": 5,
            },
            auto_verified_attributes=["email"],
            username_attributes=["email"],
        )

        self.groups = {}

        for grpname, grpcfg in self.config.get("groups", default={}).items():
            # Create basic groups
            self._add_cape_group(grpname, grpcfg)

        self.local_users = []

        for usrcfg in self.config.get("users", default=[]):
            self._add_cape_user(usrcfg, self.user_pool.id)

        # now that we've loaded our groups and local users from the config file,
        # we're going to also grab the extras files (untracked files containing
        # stuff that shouldn't be in the repo) and create users and groups from
        # those.

        extra_grps_file = self.config.get("groups_extra", default=None)
        extra_usrs_file = self.config.get("users_extra", default=None)

        if extra_grps_file is not None:
            self.load_groups_file(extra_grps_file)

        if extra_usrs_file is not None:
            self.load_users_file(extra_usrs_file, self.user_pool.id)

        # TODO: configure external providers with IdentifyProvider
        # aws.cognito.IdentityProvider("name", user_pool_id=self.user_pool.id,
        #                              provider_name="GTRI", provider_type="OIDC",
        #                              ...)

        # Create app clients (jupyerhub, eventually add cape-ui)
        self.clients = {
            client: aws.cognito.UserPoolClient(
                f"client-{client}",
                name=client,
                user_pool_id=self.user_pool.id,
                generate_secret=True,
                allowed_oauth_flows_user_pool_client=True,
                allowed_oauth_flows=["code"],
                supported_identity_providers=["COGNITO"],
                **options,  # pyright: ignore
            )
            for client, options in (
                {
                    "jupyterhub": {
                        "callback_urls": [
                            "https://jupyterhub.cape-dev.org/hub/oauth_callback"
                        ],
                        "allowed_oauth_scopes": ["openid", "email"],
                    }
                }
            ).items()
        }

        # TODO: Create identity pool cape-identities

        # TODO: add cognito IDP to identity pool and add default mappings for basic role

        # TODO: add cognito IDP mappings for special claims to more specific roles

    def _add_cape_group(self, grpname: str, grpcfg: dict[str, Any]):
        """Create a CAPE group and add it to the local tracking dict.

        The config dict has the form:
        {
            "name": <group name: str>,
            "description": <description: str>,
            "precedence": <group precedence: int>,
        }

        Args:
            grpname: The name for the group.
            grpcfg: The configuration dict for the group.
        """

        self.groups[grpname] = aws.cognito.UserGroup(
            f"{capeinfra.stack_ns}-grp-{grpname}",
            user_pool_id=self.user_pool.id,
            **grpcfg,
        )

    def _add_cape_user(self, usrcfg: dict[str, Any], user_pool_id: Output):
        """Create a CAPE user and add it to the local tracking list.

        The config dict has the form:
        {
            "email": <user email (which is username): str>,
            "groups": <group names list: list[str]>,
        }

        The groups named in the list must already exist or be in the process of
        being deployed. The user will be added to these groups whgen created.

        Args:
            usrcfg: The configuration dict for the user.
            user_pool_id: The id of the user pool to add the user to.
        """
        # TODO:
        # * add IdP/provider column
        # * wire up email verification
        # * handle users that should not have a default password (e.g. when we
        #   have external IdPs, we shouldn't be having a default password as
        #   the PW is managed by the external system)
        # * when loading users from a file, they may not be local users, but we
        #   put them in the local user tracking list. we should either rename
        #   the local users list to be more generic, or only track local users
        #   in there and add something else for non-local users

        email = usrcfg["email"]

        usr = aws.cognito.User(
            f"{capeinfra.stack_ns}-usr-{email}",
            user_pool_id=user_pool_id,
            username=email,
            # NOTE: user will be prompted to change on first login
            temporary_password=usrcfg["temporary_password"],
            attributes={
                "email": email,
                "email_verified": "true",
            },
        )

        self.local_users.append(usr)
        for gname in usrcfg.get("groups", []):
            # self._add_user_to_group(email, gname, user_pool_id)
            self._add_user_to_group(
                usr.username, self.groups[gname].name, user_pool_id
            )

    def _add_user_to_group(self, uname: Output, gname: Output, user_pool_id):
        """Add a CAPE user to a CAPE group.

        Args:
            uname: The username (email) of the user.
            gname: The name of the group.
            user_pool_id: The id of the user pool the user exists in.
        """
        # NOTE: this is really broken out only in case we need to add logic here
        #       or use it ouside the flow of adding a user from scratch. If
        #       those things are never needed, this can really fold into the
        #       _add_cognito_user method.
        aws.cognito.UserInGroup(
            f"{capeinfra.stack_ns}-uig-{gname}-{uname}",
            user_pool_id=user_pool_id,
            group_name=gname,
            username=uname,
        )

    def load_groups_file(self, filepth):
        """Load an arbitrary csv file of groups and add them to CAPE.

        csv file columns are: ["name", "description", "precedence"]

        Args:
            filepth: The path to the file of extra group definitions (either
            full path or relative to repo root)
        Raises:
            ValueError - On File containing the wrong set of column headers.
            FileNotFoundException - If the provided file path is not correct.
        """
        # Doing basic column checking to make sure the file is well formed.
        expected_cols = ["name", "description", "precedence"]

        with open(filepth) as grpcsv:
            grpreader = csv.reader(grpcsv, skipinitialspace=True)
            # our first row will be column names. grab em and make sure we have
            # the set we expect.
            grpfile_cols = next(grpreader)

            if set(expected_cols) != set(grpfile_cols):
                raise ValueError(
                    f"CAPE extra groups file is malformed. Expected column "
                    f"headers {expected_cols} but received {grpfile_cols}."
                )

            for row in grpreader:
                grpcfg = dict(zip(grpfile_cols, row))
                gname = grpcfg.pop("name")
                self._add_cape_group(gname, grpcfg)

    def load_users_file(self, filepth: str, user_pool_id: Output):
        """Load an arbitrary csv file of users and add them to CAPE.

        csv file columns are: ["email", "groups"] where `groups` is a colon
        separated string of group names the user needs to be added to. These
        groups must exist or be in the process of being deployed from this
        pulumi repo.

        Args:
            filepth: The path to the file of extra user definitions (either
            full path or relative to repo root)
            user_pool_id: The user pool id the user will be added to.
        Raises:
            ValueError - On File containing the wrong set of column headers.
            FileNotFoundException - If the provided file path is not correct.
        """
        # Doing basic column checking to make sure the file is well formed.
        expected_cols = ["email", "temporary_password", "groups"]

        with open(filepth) as usrcsv:
            usrreader = csv.reader(usrcsv, skipinitialspace=True)
            # our first row will be column names. grab em and make sure we have
            # the set we expect

            usrfile_cols = next(usrreader)
            if set(expected_cols) != set(usrfile_cols):
                raise ValueError(
                    f"CAPE extra users file is malformed. Expected column "
                    f"headers {expected_cols} but received {usrfile_cols}."
                )

            for row in usrreader:
                # the groups column will be a comma separated string that we need
                # to break out into list of strings
                email, tpass, grps = row
                usrcfg = {
                    "email": email,
                    "temporary_password": tpass,
                    "groups": grps.split(":"),
                }
                self._add_cape_user(usrcfg, user_pool_id)
