"""Abstractions for batch pipelines."""

import base64
import json

import pulumi_aws as aws
from pulumi import Input, ResourceOptions

from capeinfra.iam import get_inline_role, get_instance_profile
from capeinfra.pipeline.ecr import ContainerRepository
from capepulumi import CapeComponentResource


def render_host_bootstrap_user_data(host_bootstrap: dict) -> str:
    """Render base64 user data for a capability-specific Batch host."""

    efs_mounts = host_bootstrap.get("efs_mounts")
    if not isinstance(efs_mounts, dict):
        raise ValueError("host_bootstrap.efs_mounts must be an object")

    mounts = efs_mounts.get("mounts")
    if not isinstance(mounts, list) or not mounts:
        raise ValueError("host_bootstrap.efs_mounts.mounts must be non-empty")

    required = efs_mounts.get("required")
    if required is None:
        required = True
    if not isinstance(required, bool):
        raise ValueError("host_bootstrap.efs_mounts.required must be boolean")

    mounts_json = json.dumps(
        {"version": 1, "mounts": mounts},
        separators=(",", ":"),
        sort_keys=True,
    )
    mounts_b64 = base64.b64encode(mounts_json.encode("utf-8")).decode("ascii")
    required_value = "true" if required else "false"

    script = f"""MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="==CAPE_EFS_BOOTSTRAP=="

--==CAPE_EFS_BOOTSTRAP==
Content-Type: text/cloud-boothook; charset="us-ascii"

#!/bin/bash
set -eu

install -d -m 0755 /etc/ecs
printf '%s' '{mounts_b64}' | base64 --decode > /etc/ecs/efs-mounts.json.tmp
test -s /etc/ecs/efs-mounts.json.tmp
mv /etc/ecs/efs-mounts.json.tmp /etc/ecs/efs-mounts.json
printf '%s\\n' 'ECS_EFS_MOUNTER_REQUIRED={required_value}' > /etc/ecs/efs-mounter.env.tmp
test -s /etc/ecs/efs-mounter.env.tmp
mv /etc/ecs/efs-mounter.env.tmp /etc/ecs/efs-mounter.env
chmod 0644 /etc/ecs/efs-mounts.json /etc/ecs/efs-mounter.env
# AWS Batch owns ECS startup; the systemd dependency starts the mounter later.

--==CAPE_EFS_BOOTSTRAP==--
"""
    return base64.b64encode(script.encode("utf-8")).decode("ascii")


class BatchJobDefinition(CapeComponentResource):
    """A batch job definition."""

    # TODO: policy defaults

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:datalake:BatchJobDefinition"

    def __init__(
        self,
        name: Input[str],
        properties: dict,
        repository: ContainerRepository,
        *args,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the batch job.
            properties: The AWS Batch Job containerProperties
            repository: The container repository that stores container images for lookup
        Returns:
        """
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)

        self.name = f"{name}"

        def apply_uri(uri):
            properties["image"] = uri
            return json.dumps(properties)

        json_props = (
            repository.images[properties["image"]].image.image_uri.apply(
                apply_uri
            )
            if properties["image"] in repository.images
            else json.dumps(properties)
        )

        self.job_definition = aws.batch.JobDefinition(
            self.name,
            name=self.name,
            type="container",
            container_properties=json_props,
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs(
            {
                "job_definition": self.job_definition.id,
            }
        )


class BatchCompute(CapeComponentResource):
    """A batch compute environment."""

    @property
    def default_config(self):
        return {
            "resources": {
                # A list of AWS EC2 instance types to request
                "instance_types": ["c4.large"],
                # The maximum number of vCPUs in an environment
                "max_vcpus": 16,
            }
        }

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:datalake:BatchCompute"

    def __init__(
        self,
        name: Input[str],
        vpc: aws.ec2.Vpc,
        subnets: dict[str, aws.ec2.Subnet],
        security_group_ids=None,
        *args,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the resource.
            vpc: The VPC object the BatchCompute will be created for.
            subnets: A dict of subnets names (from configuration) to subnet
                     objects which are associated with the BatchCompute
                     environment.
        Returns:
        """
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)

        self.name = f"{name}"

        # get a role for the crawler
        self.service_role = get_inline_role(
            f"{self.name}-srvc",
            f"{self.desc_name} AWS batch service role",
            "",
            "batch.amazonaws.com",
            srvc_policy_attach="arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole",
            opts=ResourceOptions(parent=self),
        )

        self.instance_role = get_inline_role(
            f"{self.name}-instnc",
            f"{self.desc_name} AWS batch instance role",
            "",
            "ec2.amazonaws.com",
            # TODO: add policy (ISSUE #73)
            srvc_policy_attach="arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role",
            opts=ResourceOptions(parent=self),
        )
        # TODO: remove when adding real policy above, this simply gives full s3
        # access (ISSUE #73)
        aws.iam.RolePolicyAttachment(
            f"{name}-instnc-s3svcroleatch",
            role=self.instance_role.name,
            policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
            opts=ResourceOptions(parent=self),
        )
        aws.iam.RolePolicyAttachment(
            f"{name}-instnc-batchsvcroleatch",
            role=self.instance_role.name,
            policy_arn="arn:aws:iam::aws:policy/AWSBatchFullAccess",
            opts=ResourceOptions(parent=self),
        )
        aws.iam.RolePolicyAttachment(
            f"{name}-instnc-efssvcroleatch",
            role=self.instance_role.name,
            policy_arn="arn:aws:iam::aws:policy/AmazonElasticFileSystemClientFullAccess",
            opts=ResourceOptions(parent=self),
        )
        self.instance_role_profile = get_instance_profile(
            f"{name}-instnc-rl",
            self.instance_role,
        )

        # Capability pools may reuse an existing group when external EFS
        # mount-target rules already trust it. The default path preserves the
        # historical environment-owned security group.
        if security_group_ids is None:
            self.security_group = aws.ec2.SecurityGroup(
                f"{self.name}-scrtygrp",
                # TODO: fine tune security group (ISSUE #77)
                # Currently does not allow any inbound requests into an instance
                # Allows all outbound requests unbounded
                egress=[
                    {
                        "from_port": 0,
                        "to_port": 0,
                        "protocol": "-1",
                        "cidr_blocks": ["0.0.0.0/0"],
                    }
                ],
                vpc_id=vpc.id,
                opts=ResourceOptions(parent=self),
            )
            compute_security_group_ids = [self.security_group.id]
        else:
            self.security_group = None
            compute_security_group_ids = security_group_ids

        self.placement_group = aws.ec2.PlacementGroup(
            f"{self.name}-plcmntgrp",
            strategy=aws.ec2.PlacementStrategy.CLUSTER,
            opts=ResourceOptions(parent=self),
        )

        # self.key_pair = aws.ec2.KeyPair(f"{self.name}-kypr")

        env_subnets = [sn.id for _, sn in subnets.items()]

        lifecycle = self.config.get("lifecycle")
        if lifecycle not in (None, "legacy"):
            raise ValueError(
                f"Unsupported Batch environment lifecycle: {lifecycle}"
            )
        preserve_legacy_resources = lifecycle == "legacy"
        compute_environment_options = ResourceOptions(parent=self)
        if preserve_legacy_resources:
            # Keep an old generation attached to its queue while a replacement
            # generation is created and promoted. AWS Batch cannot delete a
            # compute environment while its queue still references it.
            compute_environment_options = ResourceOptions(
                parent=self,
                ignore_changes=["compute_resources"],
            )

        compute_env_name = f"{self.name}-cmpt-env"
        compute_resource_args = {
            "type": "EC2",
            "instance_role": self.instance_role_profile.arn,
            # TODO: add EC2 key pair (ISSUE #77)
            # I don't think this is necessarily required if we don't plan on
            # SSHing into the machines (plus inbound requests should
            # probably be blocked anyway)
            # "ec2_key_pair": self.key_pair.key_name,
            "image_id": self.config.get("image"),
            "placement_group": self.placement_group.name,
            "security_group_ids": compute_security_group_ids,
            "subnets": env_subnets,
            **self.config.get("resources"),
        }

        self.launch_template = None
        host_bootstrap = self.config.get("host_bootstrap")
        if host_bootstrap is not None:
            image_id = self.config.get("image")
            if not image_id:
                raise ValueError(
                    f"Batch environment {self.name} requires an image "
                    "when host_bootstrap is configured"
                )
            compute_resource_args.pop("image_id")
            self.launch_template = aws.ec2.LaunchTemplate(
                f"{self.name}-lt",
                name=f"{self.name}-lt",
                image_id=image_id,
                user_data=render_host_bootstrap_user_data(host_bootstrap),
                update_default_version=True,
                opts=ResourceOptions(parent=self),
            )
            compute_resource_args["launch_template"] = (
                aws.batch.ComputeEnvironmentComputeResourcesLaunchTemplateArgs(
                    launch_template_id=self.launch_template.id,
                    version=self.launch_template.latest_version.apply(str),
                )
            )

        self.compute_environment = aws.batch.ComputeEnvironment(
            compute_env_name,
            name=compute_env_name,
            service_role=self.service_role.arn,
            type="MANAGED",
            compute_resources=aws.batch.ComputeEnvironmentComputeResourcesArgs(
                **compute_resource_args
            ),
            opts=compute_environment_options,
        )

        # TODO: figure out a good fair share policy, for now allow a job to
        # request as much as they want (ISSUE #78)
        # self.scheduling_policy = aws.batch.SchedulingPolicy(
        #     f"{self.name}-schdl-plcy",
        #     fair_share_policy={
        #         ...
        #     },
        #     opts=ResourceOptions(parent=self.compute_environment),
        # )

        self.job_queue = aws.batch.JobQueue(
            f"{self.name}-jobq",
            state="ENABLED",
            priority=5,
            # scheduling_policy_arn=self.scheduling_policy.arn, # TODO: add policy
            compute_environment_orders=[
                {
                    "order": 1,
                    "compute_environment": self.compute_environment.arn,
                }
            ],
            opts=ResourceOptions(parent=self.compute_environment),
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        outputs = {
            "compute_environment": self.compute_environment.id,
            "job_queue": self.job_queue,
        }
        if self.launch_template is not None:
            outputs["launch_template"] = self.launch_template.id
        self.register_outputs(outputs)
