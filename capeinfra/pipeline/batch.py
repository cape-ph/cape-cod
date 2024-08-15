"""Abstractions for batch pipelines."""

from typing import Sequence

import pulumi_aws as aws
from pulumi import Input, ResourceOptions

from ..iam import (
    get_inline_role,
)
from ..pulumi import DescribedComponentResource


class BatchCompute(DescribedComponentResource):
    """A batch compute environment."""

    def __init__(
        self,
        name: Input[str],
        image_id: Input[str],
        subnets: Sequence[Input[str]],
        *args,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the resource.
        Returns:
        """
        # This maintains parental relationships within the pulumi stack
        super().__init__(
            "capeinfra:datalake:BatchCompute", name, *args, **kwargs
        )

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
            "batch.amazonaws.com",
            # TODO: add policy
            srvc_policy_attach="arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role",
            opts=ResourceOptions(parent=self),
        )
        # TODO: remove when adding real policy above, this simply gives full s3
        # access
        aws.iam.RolePolicyAttachment(
            f"{name}-instnc-s3svcroleatch",
            role=self.instance_role.name,
            policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
            opts=ResourceOptions(parent=self),
        )

        self.security_group = aws.ec2.SecurityGroup(
            f"{self.name}-scrtygrp",
            egress=[  # TODO: fine tune security group
                {
                    "from_port": 0,
                    "to_port": 0,
                    "protocol": "-1",
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ],
            opts=ResourceOptions(parent=self),
        )

        self.placement_group = aws.ec2.PlacementGroup(
            f"{self.name}-plcmntgrp",
            strategy=aws.ec2.PlacementStrategy.CLUSTER,
            opts=ResourceOptions(parent=self),
        )

        # self.key_pair = aws.ec2.KeyPair(f"{self.name}-kypr")

        self.compute_environment = aws.batch.ComputeEnvironment(
            f"{self.name}-btch",
            service_role=self.service_role.arn,
            type="MANAGED",
            compute_resources=aws.batch.ComputeEnvironmentComputeResourcesArgs(
                type="EC2",
                instance_role=self.instance_role.arn,
                # ec2_key_pair=self.key_pair.key_name, # TODO: add EC2 key pair
                image_id=image_id,
                max_vcpus=16,
                min_vcpus=0,
                placement_group=self.placement_group.name,
                security_group_ids=[self.security_group.id],
                subnets=subnets,
            ),
            opts=ResourceOptions(parent=self),
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs(
            {"compute_environment": self.compute_environment.id}
        )
