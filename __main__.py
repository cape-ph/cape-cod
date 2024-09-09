"""An AWS Python Pulumi program"""

import pulumi

from capeinfra.datalake.datalake import DatalakeHouse
from capeinfra.meta.capemeta import CapeMeta
from capeinfra.swimlanes.private import PrivateSwimlane

# get the stack name once since it's a function and we'll use this a bunch to
# namespace things
CAPE_STACK_NS = pulumi.get_stack()

# we have very little length available for resource names (56 chars after taking
# into account the random 7 chars added to each name to ensure uniqueness). so
# we're going to split the stack name on `-` and only use the first char of each
# word as the namespace. fingers crossed we don't end up with stacks that
# resolve to the same thing...
stack_ns = "".join([t[0] for t in CAPE_STACK_NS.split("-")])

# general stack scaffolding
cape_meta = CapeMeta(f"{stack_ns}-meta", desc_name=f"{CAPE_STACK_NS} Meta ")

# private swimlane setup
private_swimlane = PrivateSwimlane(
    f"{stack_ns}-pvsl",
    desc_name=f"{CAPE_STACK_NS} private swimlane",
)

# here there be data
datalake_house = DatalakeHouse(
    f"{stack_ns}-dlh",
    cape_meta.automation_assets_bucket.bucket,
    desc_name=f"{CAPE_STACK_NS} private swimlane",
)
