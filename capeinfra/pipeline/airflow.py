"""Abstractions for Apache Airflow."""

import json

import pulumi_aws as aws
from pulumi import Input, Output, ResourceOptions

import capeinfra
from capeinfra.iam import (
    add_resources,
    aggregate_statements,
    get_inline_role,
)
from capeinfra.pipeline.batch import BatchCompute, BatchJobDefinition
from capepulumi import CapeComponentResource


class MwaaEnvironment(CapeComponentResource):
    """An AWS MWAA apache airflow environment.

    NOTE: this only supports MWAA airflow at this time. If/when we move to a
          managed instance or our own self-managed EC2 instance, this will need
          to change or have a new set of resources defined.
    """

    @property
    def default_config(self):
        return {"dag_path": "airflow/dags", "extra_env_args": {}}

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:datalake:MwaaEnvironment"

    @property
    def base_role_policy_statements(
        self,
    ) -> list[aws.iam.GetPolicyDocumentStatementArgsDict]:
        """Return the most basic role policy needed for an airflow environment.

        This policy just keeps the lights on. To actually be useful the policy
        will need specific CAPE resourcese that will be used in airflow
        workflows (e.g. batch, lambda, S3, etc)
        """

        if self._base_role_policy_statements is None:
            self._base_role_policy_statements = [
                {
                    "effect": "Allow",
                    "actions": "airflow:PublishMetrics",
                    "resources": [
                        f"arn:aws:airflow:{self.aws_region}:767397883306:environment/{self.mwaa_env_name}"
                    ],
                },
                {
                    "effect": "Allow",
                    "actions": [
                        "logs:CreateLogStream",
                        "logs:CreateLogGroup",
                        "logs:PutLogEvents",
                        "logs:GetLogEvents",
                        "logs:GetLogRecord",
                        "logs:GetLogGroupFields",
                        "logs:GetQueryResults",
                    ],
                    "resources": [
                        f"arn:aws:logs:{self.aws_region}:767397883306:log-group:airflow-{self.mwaa_env_name}-*"
                    ],
                },
                {
                    "effect": "Allow",
                    "actions": ["logs:DescribeLogGroups"],
                    "resources": ["*"],
                },
                {
                    "effect": "Allow",
                    "actions": ["s3:GetAccountPublicAccessBlock"],
                    "resources": ["arn:aws:s3:::*"],
                },
                {
                    "effect": "Allow",
                    "actions": "cloudwatch:PutMetricData",
                    "resources": "*",
                },
                {
                    "effect": "Allow",
                    "actions": [
                        "sqs:ChangeMessageVisibility",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                        "sqs:GetQueueUrl",
                        "sqs:ReceiveMessage",
                        "sqs:SendMessage",
                    ],
                    # this is not tied to our account as this is an aws
                    # managed environment. the `*` for account number is
                    # intentional
                    "resources": f"arn:aws:sqs:{self.aws_region}:*:airflow-celery-*",
                },
                {
                    "effect": "Allow",
                    "actions": [
                        "kms:Decrypt",
                        "kms:DescribeKey",
                        "kms:GenerateDataKey*",
                        "kms:Encrypt",
                    ],
                    # our mwaa env uses an aws-managed set of keys, so we
                    # have to explicitly deny our own account's keyspace
                    "not_resources": "arn:aws:kms:*:767397883306:key/*",
                    "conditions": [
                        {
                            "test": "StringLike",
                            "variable": "kms:ViaService",
                            "values": [f"sqs.{self.aws_region}.amazonaws.com"],
                        }
                    ],
                },
            ]
        return self._base_role_policy_statements

    def __init__(
        self,
        name: Input[str],
        vpc: aws.ec2.Vpc,
        subnets: dict[str, aws.ec2.Subnet],
        ingress_subnets: dict[str, aws.ec2.Subnet],
        aws_region: str,
        extra_policy_statements: (
            list[aws.iam.GetPolicyDocumentStatementArgsDict] | None
        ) = None,
        *args,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the resource.
            vpc: The VPC object the MwaaEnvironment will be created for.
            subnets: A dict of subnets names (from configuration) to subnet
                     objects which are associated with the MwaaCompute
                     environment.
            ingress_subnets:
        Returns:
        """
        super().__init__(name, *args, **kwargs)

        self._base_role_policy_statements = None

        self.name = f"{name}"
        self.mwaa_env_name = f"{self.name}-env"
        self.aws_region = aws_region

        # get in a var so we aren't typing super long lines anywhere
        ma_bucket = capeinfra.meta.automation_assets_bucket

        # if we were not provided the arg, we need an empty list.
        extra_policy_statements = (
            extra_policy_statements
            if extra_policy_statements is not None
            else []
        )

        # build up the full list of policy statements we need
        execution_role_policy_statements = aggregate_statements(
            # our base policy needs
            [self.base_role_policy_statements]
            # anything else we were configured for
            + [extra_policy_statements]
            # and we for sure need to read the meta assets bucket since the dags
            # are there
            # TODO: maybe make this configurable to be something other than meta
            #       assets
            + [
                ma_bucket.bucket.arn.apply(
                    lambda arn: add_resources(
                        ma_bucket.policies[ma_bucket.PolicyEnum.read]
                        + ma_bucket.policies[ma_bucket.PolicyEnum.browse]
                        + ma_bucket.policies[ma_bucket.PolicyEnum.read_pab],
                        f"{arn}/*",
                        arn,
                    )
                )
            ]
        )

        # get a role for the environment
        self.execution_role = get_inline_role(
            f"{self.name}-exctn",
            f"{self.desc_name} AWS MWAA execution role",
            "",
            ["airflow.amazonaws.com", "airflow-env.amazonaws.com"],
            statements=execution_role_policy_statements,
            opts=ResourceOptions(parent=self),
        )

        # TODO: only until we pass in tributary buckets to explicitly give
        #       access to
        aws.iam.RolePolicyAttachment(
            f"{self.name}-s3svcroleatch",
            role=self.execution_role.name,
            policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
            opts=ResourceOptions(parent=self),
        )

        # TODO: only until we pass in tributary buckets to explicitly give
        #       access to
        aws.iam.RolePolicyAttachment(
            f"{self.name}-btchsvcroleatch",
            role=self.execution_role.name,
            policy_arn="arn:aws:iam::aws:policy/AWSBatchFullAccess",
            opts=ResourceOptions(parent=self),
        )

        self.security_group = aws.ec2.SecurityGroup(
            f"{self.name}-scrtygrp",
            # TODO: fine tune security group (ISSUE #77)
            # Currently allows inbound from any of the configured subnets types
            # from the config file, but that allows redundant subs to talk to
            # non-redundants
            # Allows all outbound requests unbounded
            egress=[
                {
                    "from_port": 0,
                    "to_port": 0,
                    "protocol": "-1",
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ],
            # MWAA cluster machines need to be able to talk to one another, so
            # we'll open up ingress from the subnets we're putting the envs in
            # as well as any others specified here (e.g. vpn so users can get to
            # it)
            ingress=[
                {
                    "from_port": 0,
                    "to_port": 0,
                    "protocol": "-1",
                    "cidr_blocks": [
                        sn.cidr_block for sn in ingress_subnets.values()
                    ],
                }
            ],
            vpc_id=vpc.id,
            opts=ResourceOptions(parent=self),
        )

        # if we want to use our own keypair eventually we can. *but* we would
        # need to modify the base_role_policy_statements to use our own managed
        # keys as opposed to the aws provided ones.
        # self.key_pair = aws.ec2.KeyPair(f"{self.name}-kypr")

        self.mwaa_environment = aws.mwaa.Environment(
            self.mwaa_env_name,
            name=self.mwaa_env_name,
            source_bucket_arn=capeinfra.meta.automation_assets_bucket.bucket.arn,
            dag_s3_path=self.config.get("dag_path"),
            environment_class=self.config.get("environment_class"),
            airflow_version=self.config.get("airflow_version"),
            airflow_configuration_options=self.config.get("airflow_config"),
            execution_role_arn=self.execution_role.arn,
            network_configuration=aws.mwaa.EnvironmentNetworkConfigurationArgs(
                security_group_ids=[self.security_group.id],
                subnet_ids=[sn.id for _, sn in subnets.items()],
            ),
            opts=ResourceOptions(parent=self),
            **self.config.get("extra_env_args"),
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs(
            {
                "mwaa_environment": self.mwaa_environment.id,
            }
        )

    # TODO: feels this should be able to pass exactly one role, or be able to
    #       pass exactly one role to exactly one named batch compute env.
    # TODO: ISSUE  #338
    def configure_batch_compute_pass_role(
        self, batch_compute_envs: list[BatchCompute]
    ):
        """Configure MWAA execution role to be able to pass aws batch a role.

        This will configure this env's role to be able to pass *all* given roles
        to AWS Batch.
        """

        for bc_env in batch_compute_envs:
            name_slug = f"{bc_env.name}"
            passrole_policy_name = f"{name_slug}-pssrl-plcy"
            passrole_attch_name = f"{passrole_policy_name}-attch"

            jobq_policy_name = f"{name_slug}-jobq-plcy"
            jobq_attch_name = f"{jobq_policy_name}-attch"

            pass_role_policy = aws.iam.Policy(
                passrole_policy_name,
                name=passrole_policy_name,
                description=(
                    f"MWAA Pass role policy for {bc_env.name} Batch compute "
                    f"environment"
                ),
                policy=Output.json_dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": "iam:PassRole",
                                "Resource": [bc_env.service_role.arn],
                                "Condition": {
                                    "StringLike": {
                                        "iam:PassedToService": "batch.amazonaws.com"
                                    }
                                },
                            }
                        ],
                    }
                ),
                opts=ResourceOptions(parent=self),
            )

            aws.iam.RolePolicyAttachment(
                passrole_attch_name,
                role=self.execution_role.name,
                policy_arn=pass_role_policy.arn,
                opts=ResourceOptions(parent=self),
            )

            # and for the queue
            jobq_policy = aws.iam.Policy(
                jobq_policy_name,
                name=jobq_policy_name,
                description=(
                    f"MWAA job queue policy for {bc_env.name} Batch compute "
                    f"environment"
                ),
                policy=Output.json_dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "batch:SubmitJob",
                                    "batch:DescribeJobs",
                                ],
                                "Resource": [bc_env.job_queue.arn],
                            }
                        ],
                    }
                ),
                opts=ResourceOptions(parent=self),
            )

            aws.iam.RolePolicyAttachment(
                jobq_attch_name,
                role=self.execution_role.name,
                policy_arn=jobq_policy.arn,
                opts=ResourceOptions(parent=self),
            )

    # TODO: this is almost the same as the compute env part of
    #       configure_batch_compute_pass_role. combine as appropriate
    # TODO: ISSUE  #338
    def configure_batch_job_def_policy(
        self, batch_job_defs: list[BatchJobDefinition]
    ):
        """TBD"""

        for bjd in batch_job_defs:
            name_slug = f"{bjd.name}"
            bjd_policy_name = f"{name_slug}-pssrl-plcy"
            bjd_attch_name = f"{bjd_policy_name}-attch"

            bjd_role_policy = aws.iam.Policy(
                bjd_policy_name,
                name=bjd_policy_name,
                description=(
                    f"MWAA policy for {bjd.name} Batch Job Definition"
                ),
                # TODO: need to add policies to BatchJobDefinition
                policy=Output.json_dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "batch:SubmitJob",
                                    "batch:DescribeJobs",
                                ],
                                # TODO: on deploy, this had a `:39` appended at
                                #       the end (after res id). not sure why and
                                #       it messed things up
                                "Resource": [bjd.job_definition.arn],
                            }
                        ],
                    }
                ),
                opts=ResourceOptions(parent=self),
            )

            aws.iam.RolePolicyAttachment(
                bjd_attch_name,
                role=self.execution_role.name,
                policy_arn=bjd_role_policy.arn,
                opts=ResourceOptions(parent=self),
            )
