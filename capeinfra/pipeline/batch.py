"""Abstractions for batch pipelines."""

import json

import pulumi_aws as aws
from pulumi import Input, ResourceOptions

from capeinfra.iam import get_inline_role, get_instance_profile
from capeinfra.pipeline.ecr import ContainerRepository
from capepulumi import CapeComponentResource


class BatchJobDefinition(CapeComponentResource):
    """A batch job definition."""

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
        super().__init__(
            "capeinfra:datalake:BatchJobDefinition", name, *args, **kwargs
        )

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

    def __init__(
        self,
        name: Input[str],
        vpc: aws.ec2.Vpc,
        subnets: dict[str, aws.ec2.Subnet],
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
            vpc_id=vpc.id,
            opts=ResourceOptions(parent=self),
        )

        self.placement_group = aws.ec2.PlacementGroup(
            f"{self.name}-plcmntgrp",
            strategy=aws.ec2.PlacementStrategy.CLUSTER,
            opts=ResourceOptions(parent=self),
        )

        # self.key_pair = aws.ec2.KeyPair(f"{self.name}-kypr")

        env_subnets = [sn.id for _, sn in subnets.items()]

        compute_env_name = f"{self.name}-cmpt-env"
        self.compute_environment = aws.batch.ComputeEnvironment(
            compute_env_name,
            name=compute_env_name,
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
                image_id=self.config.get("image"),
                placement_group=self.placement_group.name,
                security_group_ids=[self.security_group.id],
                subnets=env_subnets,
                **self.config.get("resources"),
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
        self.register_outputs(
            {
                "compute_environment": self.compute_environment.id,
                "job_queue": self.job_queue,
            }
        )
