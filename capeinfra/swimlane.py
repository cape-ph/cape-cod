"""Module for swimlane related abstractions."""

from abc import abstractmethod
from enum import StrEnum, auto
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


# TODO: ISSUE #198
class SubnetType(StrEnum):
    """Enum of all reserved subnet types for a swimlane.

    The order of members of the enum is important. At a minimum it implies the
    order the subnets should be created in.

    Types are as follows:
        * `nat`: the subnet will be given a nat gateway. at present, this
                 this gateway will be an internet gateway and the NAT will be
                 for internet egress. no other gateways are yet supported
                 (meaning no private NAT)
        * `vpn`: any subnet marked as the VPN type will be configured to be a
                 target of the external client VPN setup.
        * `compute`: there is no special handling for this type at this time,
                     but the name is reserved for the future
        * `app`: there is no special handling for this type at this time, but
                 the name is reserved for the future
    """

    NAT = auto()
    VPN = auto()
    COMPUTE = auto()
    APP = auto()


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
        # self.az_assets keys are availability zone strings and values are
        # dicts of assets used in that az that other resources may need access
        # to. e.g. self.az_assets["us-east-2b"]["inet_nat_gw"] is the internet
        # facing nat gateway for az "us=east-2b"
        self.az_assets = dict[str, dict[str, Any]]()
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

    # TODO: ISSUE #198
    def _setup_nat_subnet(
        self, basename: str, az: str, routes: list, subnet: aws.ec2.Subnet
    ):
        """Associate the given subnet with a NAT GW pointed at an internet GW.

        No check is made that this subnet is in fact public facing. The NAT GW
        is setup for internet egress only.

        Args:
            basename: The string to use as the base for the resource names
            az: The name of the availability zone to create the nat in.
            subnet: The subnet to associate with an internet facing NAT GW.
        Returns:
            A new list of routes for the subent with the internet egress route
            first in the list.
        """

        eip = aws.ec2.Eip(f"{basename}-nateip")

        nat_gateway = aws.ec2.NatGateway(
            f"{basename}-natgw",
            subnet_id=subnet.id,
            allocation_id=eip.id,
        )

        # we want to return a new list of routes with the internet egress route
        # being first, and all routes we were given initially after that
        nat_sn_routes = [
            {
                # all outgoing traffic in the public subnet goes to the
                # internet gateway
                "cidr_block": "0.0.0.0/0",
                "gateway_id": self.internet_gateway.id,
            }
        ]

        nat_sn_routes.extend(routes)

        # NOTE: this is a little bit obnoxious. we pass in the AZ string to
        #       this method even though we should have access to it via the
        #       subnet object. reason being is that it's an Output property
        #       on the subnet, and if we use it as a key into az_assets (using
        #       apply()) it might not be resolved by the time we create another
        #       subnet that needs to route to it. so we bypass the resolution
        #       time by passing in a string that we know will exist when needed
        self.az_assets.setdefault(az, {}).setdefault("inet_nat_gw", nat_gateway)

        return nat_sn_routes

    # TODO: ISSUE #198
    def _check_subnet_configs(
        self,
        sn_configs: dict[str, dict[str, Any]],
        required_keys: list[str] = ["az"],
    ):
        """Check the subnet configuration values for baseline requirements.

        By default, we require an AZ to be specified for all subnets. We are
        not checking the validity of the az, nor that redundant subnets are
        in different AZs or anything else like that. In the event that a
        subclass overrides this default implementation, 'az' needs to be
        included or there could be issues in subnet creation.

        Args:
            sn_configs: A dict of subnet config dicts keyed on subnet name.
            required_keys: A list of required config keys. If any are missing,
                           deployment will halt due to a KeyError
        Raises:
            KeyError: on missing required config key.
        """

        for name, cfg in sn_configs.items():
            for rq in required_keys:
                if rq not in cfg:
                    raise KeyError(
                        f"Config for subnet {name} does not contain required key "
                        f"'{rq}'"
                    )

    # TODO: ISSUE #198
    def _resolve_subnet_dependencies(
        self, sn_configs: dict[str, dict[str, Any]]
    ):
        """Return creation-ordered dict of {name:subnet_config}.

        This is a very naive implementation of a dependency resolver. Right now
        we just ensure order based on subnet type, with nat subnets being
        handled first as we need their nat gateways available for internet
        egress for other subnets.

        Args:
            sn_configs: Unordered dict of format {sn_name: sn_config}.
        Returns:
            A dict who's insertion order is the order in which subnets should be
            created.
        """
        ordered_subnet_configs = {}
        processed_keys = []

        # SubnetType members are in the order we're going to create subnets in.
        # As we use a string enum for that, we can't really sort the items based
        # on the enum as it wants to use lexicographical sort. We could make
        # ge/le methods in the enum class to support that i guess, but we could
        # also just accept a small performance hit for multiple loops here as
        # it will just slow the deployment down by a tad. In reality we may
        # come up with a better dependency resolution algo anyway that could
        # make any optimizaion done now useless anyway. So multiple loops it
        # is...

        # first insert all the subnets with known types from our enumeration
        # NOTE: the for...in here is in the order we want due to how SubnetType
        #       is created. Don't go mucking with the order of types.
        for sn_type in SubnetType:
            for sn_name, sn_cfg in sn_configs.items():
                if sn_type == sn_cfg.get("type", None):
                    ordered_subnet_configs[sn_name] = sn_cfg
                    processed_keys.append(sn_name)

        # now add everything else that has a type we don't know about
        ordered_subnet_configs.update(
            {k: v for k, v in sn_configs.items() if k not in processed_keys}
        )

        # and return the sorted dict
        return ordered_subnet_configs

    # TODO: ISSUE #198
    def _create_route_list(self, sn_name: str, rte_cfgs: dict[str, dict]):
        """Return a list of routes formatted for creating a route table.

        Args:
            sn_name: The name of the subnet the routes are being created for.
            rte_cfgs: A dict of the form {subnet_cfg_name: subnet_cfg} used for
                      creating routes based on names from the config file.
        Returns:
            A list of dicts containing cidr_block and a an id of a gateway to
            route to. This will have a different key based on if the gateway is
            a NAT (`nat_gateway_id`) or another subnet (`gateway_id`).
        """

        routes = []

        for rte, rcfg in rte_cfgs.items():
            if rcfg is None:
                warn(
                    f"Subnet {sn_name} is configured to have a route to "
                    f"a subnet ({rte}) that is not found. This route will "
                    "be ignored."
                )
                continue
            # NOTE: special handling for the NAT routes. we
            #       assume in this case we're reouting all traffic to the
            #       NAT. this may be a bad assumption in the future
            if rcfg["type"] == SubnetType.NAT:
                # in this case, we need to add a route to the nat gateway
                # for the availiblity zone that routed to subnet is created
                # in
                # NOTE: this does allow a subnet in one AZ to route to a
                #       subnet in a different AZ if configured that way.
                routes.append(
                    {
                        # all outgoing traffic in the compute subnet goes to the
                        # NAT gateway
                        "cidr_block": "0.0.0.0/0",
                        "nat_gateway_id": self.az_assets[rcfg["az"]][
                            "inet_nat_gw"
                        ].id,
                    }
                )
            else:
                # in this case we assume we're setting up a route from a
                # private VPC subnet to another private VPC subnet, so local
                # routing
                routes.append(
                    {
                        "cidr_block": rcfg["cidr_block"],
                        "gateway_id": "local",
                    }
                )

        return routes

    # TODO: ISSUE #198
    def _create_subnet_route_table(
        self, sn_res_name: str, routes: list, subnet: aws.ec2.Subnet
    ):
        """Create the route table for the subnet with the given routes list.

        Args:
            sn_res_name: The resource name of the subnet. Used as a prefix in
                         ComponentResource naming.
            routes: List of route definition dicts. Dicts contain a `cidr_block`
                    item and a gateway id (with key depending on gateway type)
                    to route traffic for that CIDR to.
            subnet: The subnet object the route table is being constructed for.
        """
        subnet_rt = aws.ec2.RouteTable(
            f"{sn_res_name}-rt",
            vpc_id=self.vpc.id,
            routes=routes,
        )

        aws.ec2.RouteTableAssociation(
            f"{sn_res_name}-rtassn",
            subnet_id=subnet.id,
            route_table_id=subnet_rt.id,
        )

    # TODO: ISSUE #198
    def _setup_subnet(
        self,
        sn_res_name: str,
        sn_cfg: dict[str, Any],
        rte_cfgs: dict[str, dict],
        subnet: aws.ec2.Subnet,
    ):
        """Handle setup and routing for subnet types.

        Only NAT subnets are currently handled specially.

        Args:
            sn_type: The type of subnet being handled.
            sn_res_name: The resource name of the subnet.
            az: The availability zone the subnet is being configured in.
            subnet: The subnet object requiring special setup.
        """

        routes = self._create_route_list(sn_cfg["name"], rte_cfgs)

        if sn_cfg["type"] == SubnetType.NAT:
            # add a NAT gateway and get a new list of routes that includes
            # routing to the nat
            routes = self._setup_nat_subnet(
                sn_res_name, sn_cfg["az"], routes, subnet
            )

        self._create_subnet_route_table(sn_res_name, routes, subnet)

    def create_subnets(self):
        """Default implementation of private subnet creation for a swimlane.

        The default implementation sets up the subnets as configured and routes
        all outgoing traffic to the NAT gateway in the public subnet if
        configured.
        """

        # we need this to create a lookup for route configuration in addition
        # to iteration below. we will need to create the nat (public) subnets
        # first as we will need their nat gateway ids for any other subnets
        # requiring agress to the internet
        named_pscs = {
            psnc["name"]: psnc
            for psnc in self.config.get("subnets", default=[])
        }

        # make sure subnets meet baseline to continue
        self._check_subnet_configs(named_pscs)

        # get an ordered version of this dict so that we can make the subnets in
        # an order without dependency issues

        ordered_pscs = self._resolve_subnet_dependencies(named_pscs)

        # TODO: ISSUE #118
        for sn_name, sn_cfg in ordered_pscs.items():
            sn_cfg = CapeConfig(sn_cfg)

            # devowel the configured name to try to save some characters in max
            # string lengths for identifiers when constructing the subnet
            # resource name
            sn_res_name = f"{self.basename}-{disemvowel(sn_name)}sn"

            # Unless specified as True, subnets will be private
            is_public = sn_cfg.get("make_public", False)

            # TODO: ISSUE #198
            subnet = aws.ec2.Subnet(
                sn_res_name,
                # TODO: ISSUE #198
                cidr_block=sn_cfg.get("cidr-block"),
                vpc_id=self.vpc.id,
                availability_zone=sn_cfg.get("az"),
                map_public_ip_on_launch=is_public,
                tags={
                    "Name": f"{sn_res_name} ({sn_name})",
                    "desc_name": (
                        f"{self.desc_name} {sn_name} ("
                        f"{'public' if is_public else 'private'} "
                        f"{sn_cfg['type']}) subnet"
                    ),
                },
            )

            rte_cfgs = {}

            for rte in sn_cfg.get("routes", default=[]):
                rte_cfgs[rte] = ordered_pscs.get(rte, None)

            # do any type-specific setup for the subnet
            self._setup_subnet(sn_res_name, sn_cfg, rte_cfgs, subnet)

            self.subnets[sn_name] = (sn_cfg["type"], subnet)

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
                subnets=self.get_subnets_by_type(SubnetType.COMPUTE),
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
