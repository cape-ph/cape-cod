"""An AWS Python Pulumi program"""

import pulumi

from capeinfra.datalake.datalake import DatalakeHouse
from capeinfra.meta.capemeta import CapeMeta

# get the stack name once since it's a function and we'll use this a bunch to
# namespace things
CAPE_STACK_NS = pulumi.get_stack()

# general stack scaffolding
cape_meta = CapeMeta(f"{CAPE_STACK_NS}-meta")

# here there be data
datalake_house = DatalakeHouse(
    f"{CAPE_STACK_NS}-datalakehouse", cape_meta.automation_assets_bucket.bucket
)
