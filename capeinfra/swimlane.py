"""Module for swimlane related abstractions."""

from abc import abstractmethod

import pulumi_aws as aws
from pulumi import Config, ResourceOptions

from capeinfra.util.naming import disemvowel

from .pulumi import DescribedComponentResource


class ScopedSwimlane(DescribedComponentResource):
    """Base class for all scoped swimlanes.

    A scoped swimlane is the logical grouping of public, protected or private
    resources in the CAPE infra.
    """

    def __init__(self, basename, *args, **kwargs):
        # This maintains parental relationships within the pulumi stack
        super().__init__(self.type_name, basename, *args, **kwargs)
        self._cfg_dict = None
        self._inet_gw = None
        self.basename = basename
        self.create_vpc()
        self.create_public_subnet()
        self.create_private_subnets()
        self.register_outputs({f"{self.basename}-vpc-id": self.vpc.id})

    @property
    @abstractmethod
    def type_name(self) -> str:
        """Abstract property to get the type_name (pulumi namespacing)."""
        pass

    @property
    @abstractmethod
    def scope(self) -> str:
        """Abstract property to get the scope (public, protected, private)."""
        pass

    @property
    @abstractmethod
    def default_cfg(self) -> dict:
        """Abstract property to get the type_name (pulumi namespacing)."""
        pass

    @property
    def basename(self):
        """Return the basename of the swimlane."""
        return self._swimlane_name

    @basename.setter
    def basename(self, name):
        """Set the basename property of the swimlane."""
        self._swimlane_name = name

    @property
    def vpc_name(self):
        """Return the VPC name for the swimlane."""
        return self._vpc_name

    @vpc_name.setter
    def vpc_name(self, name):
        """Set the VPC name for the swimlane."""
        self._vpc_name = name

    @property
    def internet_gateway(self):
        """Return the internet gateway for the VPC.

        If the gateway has not been created yet, it will be created."""
        if self._inet_gw is None:
            self._inet_gw = aws.ec2.InternetGateway(
                f"{self.vpc_name}-igw", vpc_id=self.vpc.id
            )

        return self._inet_gw

    def get_config_dict(self):
        """Gets the config dict for the swimlane based on its setup.

        Returns:
            The configuration dict for the swimlane. This comes from the pulumi
            config under the key `cape-cod:swimlanes`
        """
        if self._cfg_dict is None:
            config = Config("cape-cod")
            all_sl_config = config.require_object("swimlanes")
            self._cfg_dict = all_sl_config.get(self.scope, self.default_cfg)
        return self._cfg_dict

    def create_vpc(self):
        """Create the VPC for the swimlane."""
        self.vpc_name = f"{self.basename}-vpc"

        self.vpc = aws.ec2.Vpc(
            self.vpc_name,
            args=aws.ec2.VpcArgs(
                cidr_block=self.get_config_dict().get(
                    "cidr-block", self.default_cfg["cidr-block"]
                ),
                enable_dns_hostnames=True,
                enable_dns_support=True,
                # NOTE: to set the name of a VPC resource (the name that's
                #       visible within AWS), you have to add a tag with the key
                #       `Name`. this is the only resource encountered to date
                #       that acts that way. yay consistency :smh:
                tags={
                    "Name": self.vpc_name,
                    "desc_name": f"{self.desc_name} VPC",
                },
            ),
            opts=ResourceOptions(parent=self),
        )

    def create_public_subnet(self):
        """Default implementation of public subnet creation for a swimlane.

        The default implementation sets up the subnet as configured and adds a
        NAT gateway for private subnet instances to send requests to the
        internet. Additionally all outgoing traffic is routed to the swimlane's
        internet gateway.
        """
        pubsn_name = f"{self.vpc_name}-pubsn"
        self.public_subnet = aws.ec2.Subnet(
            pubsn_name,
            vpc_id=self.vpc.id,
            cidr_block=self.get_config_dict()
            .get("public-subnet", self.default_cfg["public-subnet"])
            .get("cidr-block", None),
            map_public_ip_on_launch=True,
            tags={
                "Name": pubsn_name,
                "desc_name": f"{self.desc_name} public subnet",
            },
        )

        eip = aws.ec2.Eip(f"{self.vpc_name}-nat-eip")

        self.nat_gateway = aws.ec2.NatGateway(
            f"{self.vpc_name}-natgw",
            subnet_id=self.public_subnet.id,
            allocation_id=eip.id,
        )

        public_rt = aws.ec2.RouteTable(
            f"{pubsn_name}-rt",
            vpc_id=self.vpc.id,
            routes=[
                {
                    # all outgoing traffic in the public subnet goes to the
                    # internet gateway
                    "cidr_block": "0.0.0.0/0",
                    "gateway_id": self.internet_gateway.id,
                }
            ],
        )

        aws.ec2.RouteTableAssociation(
            f"{pubsn_name}-rtassn",
            subnet_id=self.public_subnet.id,
            route_table_id=public_rt.id,
        )

    def create_private_subnets(self):
        """Default implementation of private subnet creation for a swimlane.

        The default implementation sets up the subnets as configured and routes
        all outgoing traffic to the NAT gateway in the public subnet if
        configured.
        """
        # private_sn_configs = self.get_config_dict().get("private-subnets", self.default_cfg["private-subnets"])

        for psnc in self.get_config_dict().get(
            "private-subnets", self.default_cfg["private-subnets"]
        ):
            config_sn_name = psnc.get("name")
            # devowel the configured name to try to save some characters in max
            # string lengths for identifiers when constructing the subnet name
            sn_name = f"{self.basename}-{disemvowel(config_sn_name)}sn"
            subnet = aws.ec2.Subnet(
                sn_name,
                cidr_block=psnc.get("cidr-block"),
                vpc_id=self.vpc.id,
                tags={
                    "Name": sn_name,
                    "desc_name": f"{self.desc_name} analysis {sn_name} subnet",
                },
            )

            if psnc.get("egress-to-nat", False):
                subnet_nat_rt = aws.ec2.RouteTable(
                    f"{sn_name}-rt",
                    vpc_id=self.vpc.id,
                    routes=[
                        {
                            # all outgoing traffic in the compute subnet goes to the
                            # NAT gateway
                            "cidr_block": "0.0.0.0/0",
                            "nat_gateway_id": self.nat_gateway.id,
                        }
                    ],
                )

                aws.ec2.RouteTableAssociation(
                    f"{sn_name}-rtassn",
                    subnet_id=subnet.id,
                    route_table_id=subnet_nat_rt.id,
                )
