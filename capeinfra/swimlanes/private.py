"""Resources for CAPE infra specific to the private swimlane.

This includes the private VPC, API/VPC endpoints and other top-level resources.
"""

import pulumi_aws as aws
from pulumi import ResourceOptions

from ..swimlane import ScopedSwimlane


class PrivateSwimlane(ScopedSwimlane):
    """Contains resources for the private swimlane of the CAPE Infra."""

    def __init__(self, name, opts=None):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, opts)

        self.vpc = aws.ec2.Vpc(
            f"{name}-vpc",
            args=aws.ec2.VpcArgs(
                cidr_block=self.get_config_dict().get(
                    "cidr-block", self.default_cfg["cidr-block"]
                ),
                enable_dns_hostnames=True,
                enable_dns_support=True,
            ),
            opts=ResourceOptions(parent=self),
        )

        # Nothing to register at this time, but call to signal to pulumi that
        # we're done
        self.register_outputs({})

    @property
    def type_name(self) -> str:
        """Implementation of abstract property `type_name`.

        Returns:
            The type name (pulumi namespacing) for the resource.
        """
        return "capeinfra:swimlanes:PrivateSwimlane"

    @property
    def scope(self) -> str:
        """Implementation of abstract property `scope`.

        Returns:
            The scope (public, protected, private) of the swimlane.
        """
        return "private"

    @property
    def default_cfg(self) -> dict:
        """Implementation of abstract property `default_cfg`.

        Returns:
            The default config dict for this swimlane.
        """
        return {
            # by default (if not overridden in config) this will get ip space
            # 10.0.0.0-255
            "cidr-block": "10.0.0.0/24",
        }
