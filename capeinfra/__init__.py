import pulumi

from capeinfra.meta.capemeta import CapeMeta

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
meta = CapeMeta(f"{stack_ns}-meta", desc_name=f"{CAPE_STACK_NS} Meta ")
