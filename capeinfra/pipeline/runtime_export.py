"""Build the Pulumi handoff consumed by environment deployment tooling."""

from __future__ import annotations

from typing import Any

import pulumi


PIPELINE_ASSET_ROOT_PREFIX = "pipelines/"
PIPELINE_ASSET_MANIFEST_PREFIX = "pipelines/manifests/"
PIPELINE_SHARED_DATABASE_PREFIX = "pipelines/shared/databases/"


def _resolve_route_resource_key(swimlane: Any, route: Any) -> str:
    """Resolve one configured execution route to a Batch resource key."""
    if isinstance(route, str):
        return route
    if isinstance(route, dict):
        resource_key = route.get("resource_key")
        if resource_key is not None:
            return resource_key
        environment_name = route.get("environment")
        generation = route.get("generation")
        resource_key = swimlane.batch_compute_environment_keys.get(
            (environment_name, generation)
        )
        if resource_key is not None:
            return resource_key
    raise ValueError(f"Invalid execution route definition: {route}")


def _resource_reference(resource: Any) -> pulumi.Output[dict[str, Any]]:
    """Return resolved name and ARN values for one AWS resource."""
    return pulumi.Output.all(name=resource.name, arn=resource.arn)


def build_pipeline_runtime_export(
    private_swimlane: Any,
    meta: Any,
    stack: str,
    region: str,
    account_id: Any,
) -> pulumi.Output[dict[str, Any]]:
    """Build a stable infrastructure handoff for pipeline deployment tooling."""
    meta_bucket = meta.automation_assets_bucket.bucket
    pipeline_registry = private_swimlane.analysis_pipeline_registry.analysis_pipeline_registry_ddb_table
    workflow_registry = private_swimlane.workflow_meta_registry.workflow_meta_ddb_table.ddb_table
    nextflow_job_definition = private_swimlane.job_definitions[
        "nextflow"
    ].job_definition

    execution_routes = private_swimlane.config.get(
        "compute", "execution_routes", default={}
    )
    route_resources = {}
    for execution_class, route in execution_routes.items():
        resource_key = _resolve_route_resource_key(private_swimlane, route)
        route_resources[execution_class] = _resource_reference(
            private_swimlane.batch_compute_environments[resource_key].job_queue
        )

    workflow_queue = private_swimlane.batch_compute_environments[
        _resolve_route_resource_key(
            private_swimlane,
            execution_routes.get("workflow-orchestration") or "workflows",
        )
    ].job_queue
    analysis_queue = private_swimlane.batch_compute_environments[
        _resolve_route_resource_key(
            private_swimlane,
            execution_routes.get("general-analysis") or "analysis",
        )
    ].job_queue
    route_export = pulumi.Output.all(**route_resources)

    outputs = {
        "account_id": account_id,
        "assets_bucket": meta_bucket.bucket,
        "assets_bucket_arn": meta_bucket.arn,
        "pipeline_registry_name": pipeline_registry.name,
        "pipeline_registry_arn": pipeline_registry.arn,
        "workflow_registry_name": workflow_registry.name,
        "workflow_registry_arn": workflow_registry.arn,
        "nextflow_job_definition_name": nextflow_job_definition.name,
        "nextflow_job_definition_arn": nextflow_job_definition.arn,
        "workflow_queue": _resource_reference(workflow_queue),
        "analysis_queue": _resource_reference(analysis_queue),
        "route_resources": route_export,
    }

    return pulumi.Output.all(**outputs).apply(
        lambda resolved: {
            "schemaVersion": 1,
            "environment": stack,
            "region": region,
            "accountId": resolved["account_id"],
            "pipelineAssets": {
                "bucket": resolved["assets_bucket"],
                "arn": resolved["assets_bucket_arn"],
                "rootPrefix": PIPELINE_ASSET_ROOT_PREFIX,
                "manifestPrefix": PIPELINE_ASSET_MANIFEST_PREFIX,
                "sharedDatabasePrefix": PIPELINE_SHARED_DATABASE_PREFIX,
            },
            "pipelineRuntime": {
                "dapRegistryTable": {
                    "name": resolved["pipeline_registry_name"],
                    "arn": resolved["pipeline_registry_arn"],
                },
                "workflowRegistryTable": {
                    "name": resolved["workflow_registry_name"],
                    "arn": resolved["workflow_registry_arn"],
                },
                "nextflowJobDefinition": {
                    "name": resolved["nextflow_job_definition_name"],
                    "arn": resolved["nextflow_job_definition_arn"],
                },
                "workflowQueue": resolved["workflow_queue"],
                "analysisQueue": resolved["analysis_queue"],
                "executionRoutes": resolved["route_resources"],
            },
        }
    )
