"""Module of various AWS database abstractions (e.g. DynamoDB)."""

from collections.abc import Sequence
from enum import Enum
from typing import Any

import pulumi_aws as aws
from pulumi import Output, ResourceOptions, info, warn

from capepulumi import CapeComponentResource


class DynamoTable(CapeComponentResource):
    """A DynamoDB table."""

    class PolicyEnum(str, Enum):
        """Enum of supported policy names for this component."""

        read = "read"

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:resources:database:DynamoTable"

    def __init__(
        self,
        name,
        hash_key: str,
        idx_attrs: Sequence[
            aws.dynamodb.TableAttributeArgs
            | aws.dynamodb.TableAttributeArgsDict
        ],
        range_key: str | None = None,
        **kwargs,
    ):

        # This maintains parental relationships within the pulumi stack
        super().__init__(name, **kwargs)

        self.name = name
        # HACK: store the passed in range key because getting range key from the
        # generated table is unstable for checking if it exists or not
        self.range_key = range_key

        self.ddb_table = aws.dynamodb.Table(
            f"{self.name}-ddbt",
            name=f"{self.name}-DDBT",
            # NOTE: Eventually we'll want to get a handle on the usage of all
            #       our DDB tables so we can consider moving to "PROVISIONED"
            #       instead of "PAY_PER_REQUEST". We'd probably be much
            #       cheaper to go that route if we have a really solid idea of
            #       how many reads/writes each table needs. at that point we'll
            #       want to be able to set this via params in the `DynamoTable`
            #       caonstructor
            billing_mode="PAY_PER_REQUEST",
            hash_key=hash_key,
            range_key=range_key,
            attributes=idx_attrs,
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (f"{self.desc_name} DynamoDB Table"),
            },
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"dynamo_table_name": self.ddb_table.name})

    @property
    def policies(self) -> dict[
        str,
        list[aws.iam.GetPolicyDocumentStatementArgsDict],
    ]:
        if self._policies is None:
            self._policies = dict[
                str,
                list[aws.iam.GetPolicyDocumentStatementArgsDict],
            ]()
            self._policies[self.PolicyEnum.read] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "dynamodb:DescribeTable",
                        "dynamodb:GetItem",
                        # TODO: arguably we don't need to include scan here.
                        #       scan reads the whole table (or a bunch of the
                        #       table) at once. we grant it currently for the
                        #       API endpoints that need it, but that's the
                        #       only place we grant it.
                        "dynamodb:Scan",
                    ],
                }
            ]
        return self._policies

    # TODO: dict[Any, Any] here was to punt on a type hinting need. should be
    #       resolved.
    def add_table_item(
        self, name: str, item: dict[str, dict[str, Any]] | dict[Any, Any]
    ):
        """Add an item to the table.

        For more information on DynamoDB Attribute Value format, see here:
        https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_AttributeValue.html

        Args:
            name: A name for the item. This will be part of the full AWS
                  resource name and should be kept as short as possible.
            item: A dict representing the item to add. The values of the dict
                  *must* themselves be dicts in the DynamoDB attribute format
                  and the values of the subdicts may contain Pulumi Output
                  values.
        """

        aws.dynamodb.TableItem(
            f"{self.name}-{name}-ddbitem",
            table_name=self.ddb_table.name,
            hash_key=self.ddb_table.hash_key,
            range_key=(
                self.ddb_table.range_key.apply(lambda rk: f"{rk}")
                if self.range_key
                else None
            ),
            item=Output.json_dumps(item),
            opts=ResourceOptions(parent=self),
        )


class RDSInstance(CapeComponentResource):
    """An RDS EC2 Instance."""

    class PolicyEnum(str, Enum):
        """Enum of supported policy names for this component."""

        # TODO: these will need updated as we deal with new things like
        #       snapshotting (create/restore), clustering (if needed), etc

        # write access
        createdbinstance = "createdbinstance"
        deletedbinstance = "deletedbinstance"
        modifydbinstance = "modifybinstance"
        rebootdbinstance = "rebootdbinstance"
        startdbinstance = "startdbinstance"

        # list access
        describedbinstances = "describebinstances"

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:resources:database:RDSInstance"

    def __init__(
        self,
        name,
        subnet_group,
        db_name="cape_env_db",
        instance_class=aws.rds.InstanceType.T4_G_SMALL,
        engine="postgres",
        engine_version="18.2",
        port=5432,
        username="postgres",
        extra_rds_kwargs=None,
        **kwargs,
    ):

        # This maintains parental relationships within the pulumi stack
        super().__init__(name, **kwargs)

        self.name = name
        # setup our kwargs for the RDS instance based on named kwargs in the
        # RDSInstance constructor. we can update that with values from
        # extra_rds_kwargs. keys in the rds_kwargs dict **cannot** be
        # overwritten with extra_rds_kwargs
        rds_kwargs = {
            # TODO: specifying an az is not compatible with multi-az. need to
            #       figure out which is more important.
            # "availability_zone": availability_zone,
            "db_name": db_name,
            "db_subnet_group_name": subnet_group.name,
            "enabled_cloudwatch_logs_exports": [
                "postgresql",
                "upgrade",
                "iam-db-auth-error",
            ],
            "engine": engine,
            "engine_version": engine_version,
            "identifier": f"{self.name}-rdsinst",
            "instance_class": instance_class,
            "manage_master_user_password": True,
            "port": port,
            "username": username,
            "opts": ResourceOptions(parent=self),
            "tags": {
                "desc_name": self.desc_name,
            },
        }

        if extra_rds_kwargs is not None:
            # pop any rds_kwargs keys from extra_rds_kwargs as we don't allow
            # those to be overeridden here
            for k in rds_kwargs.keys():
                if k in extra_rds_kwargs:
                    warn(
                        f"Ignoring configured RDS extra_rds_kwarg key {k}. "
                        f"This value key is either a named parameter to "
                        f"the CAPE RDSInstance constructor or is not allowed "
                        f"to be overridden from our default."
                    )
                    extra_rds_kwargs.pop(k)

            # now we need to see if a password is specified in the extra
            # kwargs. If so we will remove all the stuff that tells AWS to
            # manage the password.
            if "password" in extra_rds_kwargs:
                info(
                    "`password` is specified in RDS configuration. Turning "
                    "off AWS password management. The password will need to "
                    "be specified in the cape-cod-env deployment repo as well."
                )

                rds_kwargs.pop("manage_master_user_password")

                if "master_user_secret_kms_key_id" in extra_rds_kwargs:
                    warn(
                        "`master_user_secret_kms_key_id` is specified in RDS "
                        "config with a password. These are mutually exclusive "
                        "and the KMS key will be ignored."
                    )
                    extra_rds_kwargs.pop("master_user_secret_kms_key_id")

            # now update the rds_kwargs dict with the extra configged values
            rds_kwargs.update(extra_rds_kwargs)

        # TODO:
        # - backups? delete protection?
        # - sizing (storage initial and max)
        # - certs
        # - maint windows (and by extention apply_immediately)?
        # - storage encryption?
        # - vpc sec groups
        # - there is an `apply_immediately` arg available here. after initial
        #   deployment and definition of maintenance windows this should
        #   probably be false (which is also the default), but may need to be
        #   true for the initial deploy. not sure yet.
        # - we currently allow the minor version to be upgraded, but not major
        # - we do not have backup specified. we should allow any valid pulumi
        #   arg for the instance to pass through, so this can be condfigured if
        #   needed
        # - if we want to specify a specific IAM ec2 instance profile, use
        #   `custom_iam_instance_profile`
        # - param group is where we define postgresql settings:
        #   https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.Parameters.html
        # - storage defaults to gp2 which is what we used in manual testing. we
        #   can change as needs require.
        # - when we have good security groups in the vpc, we'll want to pass one
        #   in here and pass it to the instance constructor with
        #   `vpc_security_group_id`
        # - do we need:
        #       - iam_database_authentication_enabled (we don't support this at
        #       this time)
        #       - maintenance_window
        # deletion_protection - this is an arguable one. we def don't want this
        #                       deleted in prod, but there may be cases where
        #                       we need this deletable (like if we change params
        #                       that require a reprovision, it might need to be
        #                       deleted/recreated. dunno if deletion protection
        #                       stops that)

        # NOTE: There are a ton of params we don't explicitly use for this. If
        #       they're in the config we'll silently pass them on tho. more
        #       info at the following links:
        # * https://www.pulumi.com/registry/packages/aws/api-docs/rds/instance
        # * https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_CreateDBInstance.html
        self.rds_instance = aws.rds.Instance(
            f"{self.name}-rdsinst",
            **rds_kwargs,
        )

        # if AWS is managing the master user password for the instance, report
        # the ARN to the user
        def get_rds_secret_names(secrets):
            """Returns a list of secret names.

            The RDS instance Output master_user_secrets is of type
            Sequence[InstanceMasterUserSecret]. This type contains a secret_arn
            value which this function uses to get the name of the secret.
            """
            return [
                aws.secretsmanager.get_secret(s.secret_arn).name
                for s in secrets
            ]

        if self.rds_instance.manage_master_user_password:
            self.rds_instance.master_user_secrets.apply(
                lambda us: info(
                    f"AWS manages {self.name} RDS Instance Secrets: "
                    f"{get_rds_secret_names(us)}"
                )
            )

    @property
    def policies(self) -> dict[
        str,
        list[aws.iam.GetPolicyDocumentStatementArgsDict],
    ]:
        if self._policies is None:
            self._policies = dict[
                str,
                list[aws.iam.GetPolicyDocumentStatementArgsDict],
            ]()
            # TODO: most of these actions have dependent perms. may need to to
            #       add thise explicitly here. they are listed here:
            # https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonrds.html

            self._policies[self.PolicyEnum.createdbinstance] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "rds:CreateDBInstance",
                    ],
                }
            ]
            self._policies[self.PolicyEnum.deletedbinstance] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "rds:DeleteDBInstance",
                    ],
                }
            ]
            self._policies[self.PolicyEnum.modifydbinstance] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "rds:ModifyDBInstance",
                    ],
                }
            ]
            self._policies[self.PolicyEnum.rebootdbinstance] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "rds:RebootDBInstance",
                    ],
                }
            ]
            self._policies[self.PolicyEnum.startdbinstance] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "rds:StartDBInstance",
                    ],
                }
            ]
            self._policies[self.PolicyEnum.describedbinstances] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "rds:DescribeDBInstances",
                    ],
                }
            ]
        return self._policies
