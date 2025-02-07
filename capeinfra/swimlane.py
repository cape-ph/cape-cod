"""Module for swimlane related abstractions."""

from abc import abstractmethod
from enum import StrEnum
from typing import Any

import pulumi_aws as aws
from pulumi import ResourceOptions, warn

# TODO: ISSUE #145 this import is only needed for the temporary DAP S3 handling.
#       it should not be here after 145.
from capeinfra.datalake.datalake import CatalogDatabase
from capeinfra.pipeline.batch import BatchCompute
from capeinfra.resources.certs import BYOCert
from capeinfra.resources.loadbalancer import AppLoadBalancer
from capeinfra.util.naming import disemvowel
from capepulumi import CapeComponentResource, CapeConfig


class SubnetType(StrEnum):
    """Enum of all reserved subnet types for a swimlane.

    Types are as follows:
        * `nat`: the subnet will be given a nat gateway. at present, this
                 this gateway will be an internet gateway and the NAT will be
                 for internet egress. no other gateways are yet supported
                 (meaning no private NAT)
        * `compute`: there is no special handling for this type at this time,
                     but the name is reserved for the future
        * `app`: there is no special handling for this type at this time, but
                 the name is reserved for the future
        * `vpn`: any subnet marked as the VPN type will be configured to be a
                 target of the external client VPN setup.
    """

    nat = "nat"
    compute = "compute"
    vpn = "vpn"
    app = "app"


class ScopedSwimlane(CapeComponentResource):
    """Base class for all scoped swimlanes.

    A scoped swimlane is the logical grouping of public, protected or private
    resources in the CAPE infra.
    """

    def __init__(
        self,
        basename,
        *args,
        data_catalog: CatalogDatabase | None = None,
        **kwargs,
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__(
            self.type_name,
            basename,
            *args,
            config=CapeConfig("swimlanes").get(self.scope, default={}),
            **kwargs,
        )
        self._inet_gw = None
        self.basename = basename

        # self.subnets keys are subnet names and values are tuples of subnet
        # type (str) and subnet object (aws.ec2.Subnet)
        self.subnets = dict[str, tuple[str, aws.ec2.Subnet]]()
        self.compute_environments = dict[str, BatchCompute]()
        self.albs = {}
        self.domain_name = self.config.get("domain")

        # we require a domain name for swimlanes.
        if self.domain_name is None:
            raise ValueError(
                f"{self.basename} swimlane domain is not configured to a "
                "valid value"
            )

        # TODO: ISSUE #145 this member is only needed for the temporary DAP S3
        #       handling. it should not be here after 145. if it needs to, we
        #       should probably rethink how we expose the catalog to
        #       non-datalake clients
        self.data_catalog = data_catalog

        self.create_domain_cert()
        self.create_vpc()
        self.create_subnets()
        self.create_compute_environments()
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

    def get_subnets_by_type(self, sn_type: str) -> dict[str, aws.ec2.Subnet]:
        """Get a dict of subnet names to subnets of a given type.

        Args:
            sn_type: The subnet type to filter for.
        """
        return {
            name: sn for name, (t, sn) in self.subnets.items() if t == sn_type
        }

    def create_domain_cert(self):
        """Create the domain wildcard cert for the swimlane."""
        # NOTE:not handling exception that could be thrown here as we want the
        #      pulumi operation to fail in that case.
        self.domain_cert = BYOCert.from_config(
            f"{self.basename}-byoc",
            self.config.get("tls", default=None),
            desc_name=f"BYOCert for {self.basename}",
        )

    def create_vpc(self):
        """Create the VPC for the swimlane."""
        self.vpc_name = f"{self.basename}-vpc"

        self.vpc = aws.ec2.Vpc(
            self.vpc_name,
            args=aws.ec2.VpcArgs(
                cidr_block=self.config.get("cidr-block"),
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

    def _create_public_subnet(self, cidr_block: str, sn_type: str):
        """Default implementation of public subnet creation for a swimlane.

        The default implementation sets up the subnet as configured and adds a
        NAT gateway for private subnet instances to send requests to the
        internet. Additionally all outgoing traffic is routed to the swimlane's
        internet gateway.

        Args:
            cidr_block: The cidr block for the public subnet
        """
        pubsn_name = f"{self.vpc_name}-pubsn"
        public_subnet = aws.ec2.Subnet(
            pubsn_name,
            vpc_id=self.vpc.id,
            cidr_block=cidr_block,
            map_public_ip_on_launch=True,
            tags={
                "Name": pubsn_name,
                "desc_name": f"{self.desc_name} public subnet",
            },
        )

        eip = aws.ec2.Eip(f"{self.vpc_name}-nat-eip")

        self.nat_gateway = aws.ec2.NatGateway(
            f"{self.vpc_name}-natgw",
            subnet_id=public_subnet.id,
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
            subnet_id=public_subnet.id,
            route_table_id=public_rt.id,
        )

        self.subnets["public"] = (sn_type, public_subnet)

    def _check_subnet_configs(self, sn_configs: dict[str, dict[str, Any]]):
        """Check the subnet configuration values for baseline requirements.

        Args:
            sn_configs: A dict of subnet config dicts keyed on subnet name.
        """

        for name, cfg in sn_configs.items():
            # we require an AZ to be specified for all subnets. we are not
            # checking the validity of the az, nor that redundant subnets
            # are in different AZs or anything else like that. maybe one day
            if "az" not in cfg:
                raise KeyError(
                    f"Config for subnet {name} does not contain required key "
                    "'az'"
                )

    def create_subnets(self):
        """Default implementation of private subnet creation for a swimlane.

        The default implementation sets up the subnets as configured and routes
        all outgoing traffic to the NAT gateway in the public subnet if
        configured.
        """

        # we need this to create a lookup for route configuration in addition
        # to iteration below...
        named_pscs = {
            psnc["name"]: psnc
            for psnc in self.config.get("subnets", default=[])
        }

        # TODO: ISSUE #131
        # During issue #131 this should be refactored to have the common code
        # shared between create_public_subnet and this method combined. Took
        # the shortcut of leaving create_public_subnet as-is during
        # implementation of #109. this change will probably lead to the name of
        # the public subnet changing, which will be a difference in `pulumi
        # preview`, avoiding that for now.
        # During this change, keep in mind that the public subnet must be
        # created first (as other subnets will need to route to the nat
        # gateway). We will also need to support multiple public subnets (e.g.
        # one per az)
        # TODO: during ISSUE #131, handle the make_public config option
        #       (defaults to False) and make AZ required

        # make sure subnets meet baseline to continue
        self._check_subnet_configs(named_pscs)

        pub_sn_cfg = named_pscs.pop("public")
        self._create_public_subnet(pub_sn_cfg["cidr-block"], pub_sn_cfg["type"])

        # TODO: ISSUE #118
        for psnc in self.config.get("subnets", default=[]):
            # TODO: ISSUE #131
            # temp bypass of public subnet since it was handled above
            if psnc["name"] == "public":
                continue

            psnc = CapeConfig(psnc)
            config_sn_name = psnc.get("name")
            # devowel the configured name to try to save some characters in max
            # string lengths for identifiers when constructing the subnet name
            sn_name = f"{self.basename}-{disemvowel(config_sn_name)}sn"
            subnet = aws.ec2.Subnet(
                sn_name,
                cidr_block=psnc.get("cidr-block"),
                vpc_id=self.vpc.id,
                availability_zone=psnc.get("az"),
                tags={
                    "Name": sn_name,
                    "desc_name": f"{self.desc_name} analysis {sn_name} subnet",
                },
            )

            routes = []
            for rte in psnc.get("routes", default=[]):
                # NOTE: special handling for the public subnet route. we
                #       assume in this case we're reouting all traffic to the
                #       NAT. this may be a bad assumption in the future
                if rte == "public":
                    routes.append(
                        {
                            # all outgoing traffic in the compute subnet goes to the
                            # NAT gateway
                            "cidr_block": "0.0.0.0/0",
                            "nat_gateway_id": self.nat_gateway.id,
                        }
                    )
                else:
                    # in this case we assume we're setting up a route from a
                    # private VPC subnet to another private VPC subnet, so local
                    # routing
                    routes.append(
                        {
                            "cidr_block": named_pscs[rte]["cidr_block"],
                            "gateway_id": "local",
                        }
                    )

            subnet_rt = aws.ec2.RouteTable(
                f"{sn_name}-rt",
                vpc_id=self.vpc.id,
                routes=routes,
            )

            aws.ec2.RouteTableAssociation(
                f"{sn_name}-rtassn",
                subnet_id=subnet.id,
                route_table_id=subnet_rt.id,
            )

            self.subnets[config_sn_name] = (psnc["type"], subnet)

    def create_compute_environments(self):
        """Default implementation of compute environment creation for a swimlane.

        The default implementation sets up the subnets as configured and routes
        all outgoing traffic to the NAT gateway in the public subnet if
        configured.
        """
        for env in self.config.get("compute", "environments", default=[]):
            name = env.get("name")
            self.compute_environments[name] = BatchCompute(
                name,
                vpc=self.vpc,
                subnets=self.get_subnets_by_type(SubnetType.compute),
                config=env,
            )

    def create_hosted_domain(self, domain_name: str):
        """Create a private hosted domain for the swimlane.

        NOTE: This is currently specific to AWS Route53 hosted zones.

        Args:
            domain_name: The name of the domain to register (e.g. cape-dev.org).
        """
        self.rte53_private_zone = aws.route53.Zone(
            f"{self.basename}-cape-rt53-prvtzn",
            name=domain_name,
            vpcs=[
                aws.route53.ZoneVpcArgs(vpc_id=self.vpc.id),
            ],
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} Route53 private Zone for "
                    f"{domain_name}"
                ),
            },
        )

    def create_private_hosted_dns(self, subnets):
        """Create a DNS endpoint for in the piavte hosted domain.

        The DNS endpoint will be active in the subnets given.

        Args:
            subnets: A list of subnet objects to enable the DNS endpoint in.
        """
        self.rte53_dns_ep = aws.route53.ResolverEndpoint(
            f"{self.basename}-rt53dns",
            direction="INBOUND",
            # TODO: ISSUE #112
            security_group_ids=[self.vpc.default_security_group_id],
            # TODO: ISSUE #118
            ip_addresses=[
                aws.route53.ResolverEndpointIpAddressArgs(subnet_id=sn.id)
                for sn in subnets
            ],
            protocols=[
                "Do53",
            ],
            tags={
                "desc_name": self.rte53_private_zone.name.apply(
                    lambda n: f"{self.desc_name} Route53 DNS Endpoint for {n}"
                ),
            },
            opts=ResourceOptions(parent=self),
        )

    def create_private_domain_alb_record(
        self,
        record_name: str,
        short_name: str,
        alb_id: str,
        aliases: list[dict] | None = None,
    ):
        """Create a private domain type A record and attach it to the ALB.

        NOTE: This is currently specific to AWS Route53 hosted zones.

        Args:
            record_name: The record name (e.g. subdomain.domain.tld).
            short_name: A short, unique name for the record. This is only used
                        in the resource name.
            alb_id: The identifier string of the ALB to associate the record
                    with.
            aliases: A list of dicts containing alias args for the record. The
                     dict keys must match the expected arg names of
                     RecordAliasArgs

        Returns: The new record.
        """
        raa = []
        if aliases:
            for alias in aliases:
                raa.append(aws.route53.RecordAliasArgs(**alias))
        else:
            raa.append(
                aws.route53.RecordAliasArgs(
                    evaluate_target_health=True,
                    name=self.albs[alb_id].alb.dns_name,
                    zone_id=self.albs[alb_id].alb.zone_id,
                )
            )

        return aws.route53.Record(
            f"{self.basename}-{short_name}-rt53rec",
            zone_id=self.rte53_private_zone.id,
            name=record_name,
            type=aws.route53.RecordType.A,
            aliases=raa,
            opts=ResourceOptions(parent=self),
        )

    def create_alb(
        self, alb_id: str, subnets: list, acmcert: aws.acm.Certificate
    ):
        """Create an application load balancer with some identifier.

        NOTE: This only currently handles HTTPS traffic over 443.

        Args:
            id: A string identifier for the ALB (e.g. "static" or "api")
            subnets: A list of subnets to associate the loadd balancer with.
            acmcert: The certificate to add to the HTTPS/443 listener for the
                     ALB.
        """

        # TODO: ISSUE #167 - resource name length limitations (again).
        #                    deferring problem till later by taking just the
        #                    first 3 chars of the alb_id

        short_alb = f"{alb_id[:3]}alb"
        self.albs[alb_id] = AppLoadBalancer(
            f"{self.basename}-{short_alb}",
            self.vpc.id,
            subnet_ids=[sn.id for sn in subnets],
            desc_name=f"{self.desc_name} {alb_id} Application Load Balancer",
        )

        self.albs[alb_id].add_listener(443, "HTTPS", acmcert=acmcert)
