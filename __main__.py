"""An AWS Python Pulumi program"""

import capeinfra
from capeinfra.swimlanes.private import PrivateSwimlane

# private swimlane setup
private_swimlane = PrivateSwimlane(
    f"{capeinfra.stack_ns}-pvsl",
    desc_name=f"{capeinfra.CAPE_STACK_NS} private swimlane",
)
