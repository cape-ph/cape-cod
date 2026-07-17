"""An AWS Python Pulumi program"""

import pulumi

import capeinfra
from capeinfra.authz.export import build_resource_export
from capeinfra.swimlanes.private import PrivateSwimlane

# private swimlane setup
private_swimlane = PrivateSwimlane(
    f"{capeinfra.stack_ns}-pvsl",
    desc_name=f"{capeinfra.CAPE_STACK_NS} private swimlane",
)

# ABAC resource catalog export for the environment DB / OPA sync. Retrieve the
# materialized JSON with:
#   pulumi stack output abac_resource_export --json > cape-cod-export.json
pulumi.export(
    "abac_resource_export",
    build_resource_export(capeinfra.data_lakehouse, capeinfra.CAPE_STACK_NS),
)
