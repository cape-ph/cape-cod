"""An AWS Python Pulumi program"""

import capeinfra
from capeinfra.datalake.datalake import DatalakeHouse
from capeinfra.swimlanes.private import PrivateSwimlane

# here there be data
datalake_house = DatalakeHouse(
    f"{capeinfra.stack_ns}-dlh",
    desc_name=f"{capeinfra.CAPE_STACK_NS} private swimlane",
)

# private swimlane setup
private_swimlane = PrivateSwimlane(
    f"{capeinfra.stack_ns}-pvsl",
    desc_name=f"{capeinfra.CAPE_STACK_NS} private swimlane",
)
