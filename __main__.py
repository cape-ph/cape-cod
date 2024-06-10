"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws

from capeinfra.meta.capemeta import CapeMeta

# get the stack name once since it's a function and we'll use this a bunch to
# namespace things
CAPE_STACK_NS = pulumi.get_stack()

cape_meta = CapeMeta(f"{CAPE_STACK_NS}-meta")
