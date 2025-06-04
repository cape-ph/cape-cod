"""Contains resources used by the whole CAPE infra deployment."""

import csv
import json
from typing import Any

import pulumi_aws as aws
from boto3.dynamodb.types import TypeSerializer
from pulumi import FileArchive, FileAsset, Output, ResourceOptions

import capeinfra
from capeinfra.iam import get_inline_role
from capeinfra.resources.objectstorage import VersionedBucket
from capeinfra.util.naming import disemvowel
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
        self.principals = CapePrincipals(
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
        self.user_pool_domain = aws.cognito.UserPoolDomain(
            f"{capeinfra.stack_ns}-cape-users-domain",
            domain=f"{capeinfra.stack_ns}-cape-users",
            user_pool_id=self.user_pool.id,
        )
        # Create a placeholder for user pool clients
        self.clients = {}

        # mapping of user ids to attribute dicts that will be added to the attrs
        # store
        self._user_attrs = {}

    def add_principals(self):
        """"""
        self.groups = {}

        # make the DDB table for the user attributes
        self.create_user_attribute_store()

        for grpname, grpcfg in self.config.get("groups", default={}).items():
            # Create basic groups
            self._add_cape_group(grpname, grpcfg)

        self.local_users = {}

        for usrcfg in self.config.get("users", default=[]):
            self._add_cape_user(usrcfg)

        # now that we've loaded our groups and local users from the config file,
        # we're going to also grab the extras files (untracked files containing
        # stuff that shouldn't be in the repo) and create users and groups from
        # those.

        extra_grps_file = self.config.get("groups_extra", default=None)
        extra_usrs_file = self.config.get("users_extra", default=None)

        if extra_grps_file is not None:
            self.load_groups_file(extra_grps_file)

        if extra_usrs_file is not None:
            self.load_users_file(extra_usrs_file)

        # now that we have all the users and groups parsed, add the user
        # attributes table items
        self._add_user_attrs_items()

        # TODO: configure external providers with IdentifyProvider
        # aws.cognito.IdentityProvider("name", user_pool_id=self.user_pool.id,
        #                              provider_name="GTRI", provider_type="OIDC",
        #                              ...)

        # TODO: Create identity pool cape-identities

        # TODO: add cognito IDP to identity pool and add default mappings for basic role

        # TODO: add cognito IDP mappings for special claims to more specific roles

    @property
    def default_trust_policy(self) -> Output:
        """"""
        # TODO: we have nothing handling `unauthenticated` amr at this time
        return self.identity_pool.id.apply(
            lambda i: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "Federated": "cognito-identity.amazonaws.com"
                            },
                            "Action": "sts:AssumeRoleWithWebIdentity",
                            "Condition": {
                                "StringEquals": {
                                    "cognito-identity.amazonaws.com:aud": f"{i}"
                                },
                                "ForAnyValue:StringLike": {
                                    "cognito-identity.amazonaws.com:amr": "authenticated"
                                },
                            },
                        },
                    ],
                },
            )
        )

    def add_identity_pool(self):
        """"""
        # TODO:
        # still will need work:
        # * assumes that we're only adding cognito identity providers for
        #   instance apps only.
        # * region is not parameterized in provider_name for cognito identity
        #   providers (we may need saml providers e.g.)
        # * hard coded role and policy (should be reusable and we should have a
        #   library of them)

        # TODO: refactor all this to fit into iam.py and to get roles out into a
        #       library
        self.identity_pool = aws.cognito.IdentityPool(
            f"{capeinfra.stack_ns}-idntty-pl",
            identity_pool_name="cape-identities",
            allow_unauthenticated_identities=False,
            allow_classic_flow=False,
            cognito_identity_providers=[
                {
                    "provider_name": self.user_pool.id.apply(
                        lambda i: f"cognito-idp.us-east-2.amazonaws.com/{i}"
                    ),
                    "client_id": c.id,
                    "server_side_token_check": False,
                }
                for _, c in self.clients.items()
            ],
            opts=ResourceOptions(parent=self),
        )

        # TODO: Convert this to something more configurable/matinainable
        # probably in capeinfra.iam
        cognito_role = aws.iam.Role(
            f"{capeinfra.stack_ns}-cgnt-rl",
            assume_role_policy=self.default_trust_policy,
            opts=ResourceOptions(parent=self),
        )

        # Allow S3 interaction for Cognito authenticated accounts
        aws.iam.RolePolicy(
            f"{capeinfra.stack_ns}-cgnt-rlplcy",
            role=cognito_role.id,
            policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetObject",
                                "s3:ListBucket",
                                "s3:PutObject",
                            ],
                            "Resource": [
                                "arn:aws:s3:::*/*",
                                "arn:aws:s3:::*",
                            ],
                        }
                    ],
                }
            ),
            opts=ResourceOptions(parent=self),
        )

        # Allow Athena interaction for Cognito authenticated accounts
        aws.iam.RolePolicyAttachment(
            f"{capeinfra.stack_ns}-cgnt-rlatch-AmazonAthenaFullAccess",
            role=cognito_role.name,
            policy_arn="arn:aws:iam::aws:policy/AmazonAthenaFullAccess",
            opts=ResourceOptions(parent=self),
        )

        aws.cognito.IdentityPoolRoleAttachment(
            f"{capeinfra.stack_ns}-{disemvowel('cognito-rolepolicy-attach')}",
            identity_pool_id=self.identity_pool.id,
            roles={"authenticated": cognito_role.arn},
        )

    def create_user_attribute_store(self):
        """Sets up a data store to hold user attributes."""
        # setup a DynamoDB table to hold documents containing attributes for
        # users. keyed on uid
        # NOTE: we can set up our Dynamo connections to go through a VPC
        #       endpoint instead of the way we're currently doing (using the
        #       fact that we have a NAT and egress requests to go through the
        #       boto3 dynamo client, which makes the requests go through the
        #       public internet). VPC endpoint is arguably more secure and
        #       performant as it's a direct connection to Dynamo from our
        #       clients, but it adds cost.
        self.user_attrs_ddb_table = aws.dynamodb.Table(
            f"{self.name}-usr-attrs-ddb",
            name=f"{self.name}-UserAttrsStore",
            # NOTE: this table will be accessed as needed to do grap/verify user
            #       attributes. it'll be pretty hard (at least till this is
            #       in use for a while) to come up with read/write metrics to
            #       set this table up as PROVISIONED with those values. We'd
            #       probably be much cheaper to go that route if we have a
            #       really solid idea of how many reads/writes this table needs
            billing_mode="PAY_PER_REQUEST",
            hash_key="user_id",
            range_key=None,
            attributes=[
                # NOTE: we do not need to define any part of the "schema" here
                #       that isn't needed in an index.
                {
                    "name": "user_id",
                    "type": "S",
                },
            ],
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} User Attributes DynamoDB Table"
                ),
            },
        )

    def _add_user_attrs_items(self):
        """"""
        # TODO: using an index while iterating a dict. we need unique names for
        #       the table items, but there isn't anything in the attrs dict
        #       outside user id that we can bank on being there. the UID is too
        #       long for the name, and using a pulumi Output in a resource name
        #       isn't supported.
        for idx, (uid, attrs) in enumerate(self._user_attrs.items()):

            serializer = TypeSerializer()
            serialized_attrs = {
                k: serializer.serialize(v) for k, v in attrs.items()
            }

            serialized_attrs.update(
                {"user_id": {"S": uid.apply(lambda u: f"{u}")}}
            )

            aws.dynamodb.TableItem(
                f"{self.name}-{idx}-ddbitem",
                table_name=self.user_attrs_ddb_table.name,
                hash_key=self.user_attrs_ddb_table.hash_key,
                # TODO: do we have a range key here? schema is unknown and UID
                #       is really the only thing we can bank on being there
                range_key=None,
                item=Output.json_dumps(serialized_attrs),
                opts=ResourceOptions(parent=self),
            )

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

        # TODO: maybe not best to :
        # * do all the IAM role stuff in here
        # * add a default IAM role to each group.
        # * name thins based on given group name (could be too long or have bad
        #   chars)
        # baby steps

        # make the short name for the group that is used in resource names. this
        # should not include any spaces
        grp_sname = disemvowel(grpname.replace(" ", ""))

        group_role = aws.iam.Role(
            f"{capeinfra.stack_ns}-{grp_sname}-rl",
            assume_role_policy=self.default_trust_policy,
            opts=ResourceOptions(parent=self),
        )

        # TODO: do not endeavour to know the group names in here...
        if grpname == "DefaultUsers":
            group_policy = aws.iam.Policy(
                f"{capeinfra.stack_ns}-{grp_sname}-rlplcy",
                # TODO: placeholder policy
                policy=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                # TODO: test if we can only allow read to one
                                #       bucket, but nothing else. obvi this will
                                #       have to change
                                "Effect": "Allow",
                                "Action": ["s3:GetObject"],
                                "Resource": "arn:aws:s3:::ccd-dlh-t-hai-input-raw-vbkt-s3-9e72cfa",
                            }
                        ],
                    }
                ),
            )

            aws.iam.RolePolicyAttachment(
                f"{capeinfra.stack_ns}-{grp_sname}-rpattch",
                role=group_role.name,
                policy_arn=group_policy.arn,
            )

        self.groups[grpname] = aws.cognito.UserGroup(
            f"{capeinfra.stack_ns}-grp-{grp_sname}",
            user_pool_id=self.user_pool.id,
            **grpcfg,
            role_arn=group_role.arn,
            opts=ResourceOptions(parent=self),
        )

    def _add_cape_user(self, usrcfg: dict[str, Any]):
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
        attrs_file = usrcfg.get("attrs_file", None)

        self.local_users[email] = aws.cognito.User(
            f"{capeinfra.stack_ns}-usr-{email}",
            user_pool_id=self.user_pool.id,
            username=email,
            # NOTE: user will be prompted to change on first login
            temporary_password=usrcfg["temporary_password"],
            attributes={
                "email": email,
                "email_verified": "true",
            },
            opts=ResourceOptions(parent=self),
        )

        self._parse_user_attrs(self.local_users[email], attrs_file)

        for gname in usrcfg.get("groups", []):
            self._add_user_to_group(email, gname)

    def _parse_user_attrs(self, user: aws.cognito.User, attrs_file: str | None):
        """Load a json file of user attributes and store it with the user id.

        Args:
            user: The cognito user we are tracking the attributes for.
            attrs_file: The path to the user attributes json file. This should
                        be either a full path, or relative to the repo root.
        """
        attrs = {}
        if attrs_file is not None:
            with open(attrs_file, "r") as af:
                attrs = json.load(af)

        self._user_attrs[user.id] = attrs

    def _add_user_to_group(self, uname: str, gname: str):
        """Add a CAPE user to a CAPE group.

        Args:
            uname: The username (email) of the user.
            gname: The name of the group.
            user_pool_id: The id of the user pool the user exists in.
        """
        # NOTE: this is really broken out only in case we need to add logic here
        #       or use it outside the flow of adding a user from scratch. If
        #       those things are never needed, this can really fold into the
        #       _add_cognito_user method.
        aws.cognito.UserInGroup(
            f"{capeinfra.stack_ns}-uig-{gname}-{uname}",
            user_pool_id=self.user_pool.id,
            group_name=self.groups[gname].name,
            username=self.local_users[uname].username,
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

    def load_users_file(self, filepth: str):
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
        expected_cols = ["email", "temporary_password", "groups", "attrs_file"]

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
                email, tpass, grps, attrs = row
                usrcfg = {
                    "email": email,
                    "temporary_password": tpass,
                    "groups": grps.split(":"),
                    # we want None here for any falsy value from the csv
                    "attrs_file": attrs if attrs else None,
                }
                self._add_cape_user(usrcfg)

    def add_client(self, name: str, options: dict):
        """Add a client to the user pool to create a cognito login endpoint

        Args:
            options: Options passed to aws.cognito.UserPoolClient such as
            `callback_urls` and `allowed_oauth_scopes`
            name: the client name to register
        """
        self.clients[name] = aws.cognito.UserPoolClient(
            f"client={name}",
            name=name,
            user_pool_id=self.user_pool.id,
            generate_secret=True,
            allowed_oauth_flows_user_pool_client=True,
            allowed_oauth_flows=["code"],
            supported_identity_providers=["COGNITO"],
            **options,  # pyright: ignore
        )
