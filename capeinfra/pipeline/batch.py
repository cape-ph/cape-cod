"""Abstractions for batch pipelines."""

from typing import NotRequired, Sequence, TypedDict

import pulumi_aws as aws
from pulumi import Input, ResourceOptions

from ..iam import get_inline_role, get_instance_profile
from ..pulumi import DescribedComponentResource


# NOTE: Is there a better way to define and maintain validated data structures
# in python that reesolve to a dictionary and have required/optional fields?
class BatchComputeResources(TypedDict):
    """A class for defining resources for instances in an AWS Batch compute environment

    Attributes:
        instance_types: A list of AWS EC2 instance types to request
        max_vcpus: The maximum number of vCPUs in an environment
        desired_vcpus: The desired number of vCPUs in an environment (Optional)
        min_vcpus: The minimum number of vCPUs in an environment (Optional)
    """

    instance_types: Sequence[str]
    max_vcpus: int
    desired_vcpus: NotRequired[int]
    min_vcpus: NotRequired[int]


def new_batch_compute_resources(
    instance_types: Sequence[str] = ["c4.large"],
    max_vcpus: int = 16,
    desired_vcpus: int | None = None,
    min_vcpus: int | None = None,
):
    params = {"instance_types": instance_types, "max_vcpus": max_vcpus}
    if desired_vcpus is not None:
        params["desired_vcpus"] = desired_vcpus
    if min_vcpus is not None:
        params["min_vcpus"] = min_vcpus
    return BatchComputeResources(**params)


class BatchCompute(DescribedComponentResource):
    """A batch compute environment."""

    def __init__(
        self,
        name: Input[str],
        image_id: Input[str],
        subnets: Sequence[Input[str]],
        resources: BatchComputeResources,
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
        self.instance_role_profile = get_instance_profile(
            f"{name}-instnc-rl",
            self.instance_role,
        )

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
                instance_role=self.instance_role_profile.arn,
                # TODO: add EC2 key pair (ISSUE #77)
                # I don't think this is necessarily required if we don't plan on
                # SSHing into the machines (plus inbound requests should
                # probably be blocked anyway)
                # ec2_key_pair=self.key_pair.key_name,
                image_id=image_id,
                placement_group=self.placement_group.name,
                security_group_ids=[self.security_group.id],
                subnets=subnets,
                **resources,
            ),
            opts=ResourceOptions(parent=self),
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
            f"{self.name}-job-q",
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
        self.register_outputs(
            {
                "compute_environment": self.compute_environment.id,
                "job_queue": self.job_queue,
            }
        )
