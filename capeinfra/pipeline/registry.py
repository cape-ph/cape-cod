"""Abstractions for data analysis pipeline registry."""

import json
from pathlib import Path

import pulumi_aws as aws
from boto3.dynamodb.types import TypeSerializer
from pulumi import Output, ResourceOptions, log

from capeinfra.resources.database import DynamoTable
from capeinfra.util.jinja2 import get_j2_template_from_path
from capepulumi import CapeComponentResource


class DAPRegistry(CapeComponentResource):
    """A registry for data analysis pipelines."""

    # TODO: long term it is not tenable for us to have all the config stuff for
    #       all the pipeline frameworks specified in this manner. we should
    #       consider keeping the default config in common files or something
    #       like that and then point to the file in this table
    # default nextflow config
    DEFAULT_NEXTFLOW_CONFIG = {
        "M": {
            "aws": {
                "M": {
                    "accessKey": {"S": "<YOUR S3 ACCESS KEY>"},
                    "secretKey": {"S": "<YOUR S3 SECRET KEY>"},
                    "region": {"S": "us-east-2"},
                    "client": {
                        "M": {
                            "maxConnections": {"N": "20"},
                            "connectionTimeout": {"N": "10000"},
                            "uploadStorageClass": {"S": "INTELLIGENT_TIERING"},
                            "storageEncryption": {"S": "AES256"},
                        }
                    },
                    "batch": {
                        "M": {
                            "cliPath": {"S": "/usr/bin/aws"},
                            "maxTransferAttempts": {"N": "3"},
                            "delayBetweenAttempts": {"S": "5 sec"},
                        }
                    },
                }
            }
        }
    }

    # name of the json file containing all deploy-time pipelines
    DAP_FIXTURE = "dap-fixtures.json"

    @property
    def default_config(self):
        return {
            # path in the deployment repo to the directory containing the
            # analysis pipeline fxiture json and a subdirectory of profiles
            "pipelines": "./assets/analysis-pipelines",
        }

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:pipeline:DAPRegistry"

    def __init__(
        self,
        name: str,
        *args,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the resource.
            opts: The ResourceOptions to apply to the registry resource.
        Returns:
        """
        super().__init__(name, *args, **kwargs)

        self.name = f"{name}"
        self.dap_pipelines = Path(self.config["pipelines"])

        self.create_dap_registry_table()
        self.load_pipeline_assets()

    def create_dap_registry_table(self):
        """Set up an analysis pipeline registry database table."""
        # setup a DynamoDB table to hold a mapping of pipeline names (user
        # facing names) to various config info for the running of the analysis
        # pipelines. E.g. a nextflow pipeline may have a default nextflow config
        # in the value object of its entry whereas a snakemake pipeline may have
        # a default snakemake config.
        # NOTE: we can set up our Dynamo connections to go through a VPC
        #       endpoint instead of the way we're currently doing (using the
        #       fact that we have a NAT and egress requests to go through the
        #       boto3 dynamo client, which makes the requests go through the
        #       public internet). This is arguably more secure and performant as
        #       it's a direct connection to Dynamo from our clients.
        self.analysis_pipeline_registry_ddb_table = aws.dynamodb.Table(
            f"{self.name}-ddb",
            name=f"{self.name}-DataAnalysisPipelineRegistry",
            # NOTE: this table will be accessed as needed to do submit analysis
            #       pipeline jobs. it'll be pretty hard (at least till this is
            #       in use for a while) to come up with read/write metrics to
            #       set this table up as PROVISIONED with those values. We'd
            #       probably be much cheaper to go that route if we have a
            #       really solid idea of how many reads/writes this table needs
            billing_mode="PAY_PER_REQUEST",
            hash_key="pipeline_id",
            attributes=[
                # NOTE: we do not need to define any part of the "schema" here
                #       that isn't needed in an index.
                {
                    "name": "pipeline_id",
                    "type": "S",
                },
                {
                    "name": "pipeline_name",
                    "type": "S",
                },
                {
                    "name": "version",
                    "type": "S",
                },
            ],
            global_secondary_indexes=[
                aws.dynamodb.TableGlobalSecondaryIndexArgs(
                    name="PipelineNameVerIndex",
                    key_schemas=[
                        aws.dynamodb.TableGlobalSecondaryIndexKeySchemaArgs(
                            attribute_name="pipeline_name",
                            key_type="HASH",
                        ),
                        aws.dynamodb.TableGlobalSecondaryIndexKeySchemaArgs(
                            attribute_name="version",
                            key_type="RANGE",
                        ),
                    ],
                    projection_type="ALL",
                    non_key_attributes=[],
                    read_capacity=0,
                    write_capacity=0,
                )
            ],
            opts=ResourceOptions(
                parent=self,
                # TODO: this is a bazooka against an ant. the GSI keeps showing
                #       changes in the for of adding `__defaults: []` in the GSI
                #       and each entry in the key_schemas as well as removal of
                #       the previously specified hash_key and range_key values
                #       (which were replaced by key_schemas recently). this
                #       despite the table being removed and rebuilt totally
                #       since removal of the `[hash|range]_key` fields (meaning
                #       they should no longer be involved at all). so we're
                #       ignoring all GSI changes reported from the server. which
                #       is bad if we make a real change...need to fix
                ignore_changes=["global_secondary_indexes"],
            ),
            tags={
                "desc_name": (
                    f"{self.desc_name} Analysis Pipeline Registry DynamoDB Table"
                ),
            },
        )

    def load_pipeline_assets(self):
        """Load local assets into the registry bucket and table."""

        # make sure we have a json file that defines all the deploy time
        # pipelines
        if not self.dap_pipelines.exists():
            log.warn(
                (
                    f"Unable to locate analysis pipeline fixtures file: "
                    f"{self.dap_pipelines}. No analysis pipelines will be "
                    f"deployed."
                ),
                self,
            )
            return

        # final pipelines in the registry
        pipelines = {}
        # pipeline profiles that need to be validated and resolved
        to_process_pipelines: list[tuple[str, dict]] = []
        # iterate over all JSON files in the DAP pipelines directory
        for path in self.dap_pipelines.glob("**/*.json"):
            # render JSON file as jinja template and load as JSON
            pipeline_template = get_j2_template_from_path(str(path))
            to_process_pipelines.append(
                (
                    path.stem,
                    json.loads(
                        pipeline_template.render(
                            # currently only pass AWS region, can be expanded later
                            aws_region=aws.get_region().region
                        )
                    ),
                )
            )

        while len(to_process_pipelines) > 0:
            new_to_process = []
            for stem, profile in to_process_pipelines:
                inherited_pipelines = profile.get("inherits", [])
                if all(
                    pipeline in pipelines for pipeline in inherited_pipelines
                ):
                    parameter_schema = profile.get("parametersSchema")
                    if parameter_schema:
                        parameter_schema["$defs"] = {}
                        for inherited_stem in inherited_pipelines:
                            parameter_schema["$defs"][inherited_stem] = (
                                pipelines[inherited_stem].get(
                                    "parametersSchema", {}
                                )
                            )
                    pipelines[stem] = profile
                    # Add resolved pipeline to the DynamoDB table
                    aws.dynamodb.TableItem(
                        f"{self.name}-{stem}-ddbitem",
                        table_name=self.analysis_pipeline_registry_ddb_table.name,
                        hash_key=self.analysis_pipeline_registry_ddb_table.hash_key,
                        item=Output.json_dumps(
                            {
                                "pipeline_name": {"S": profile["pipelineName"]},
                                "pipeline_id": {"S": profile["pipelineId"]},
                                "pipeline_runnable": {
                                    "BOOL": profile["pipelineRunnable"]
                                },
                                "version": {"S": profile["version"]},
                                "project": {"S": profile["project"]},
                                "pipeline_type": {"S": profile["pipelineType"]},
                                "profile": TypeSerializer().serialize(profile),
                                "nextflow_config": self.DEFAULT_NEXTFLOW_CONFIG,  # TODO: CURRENTLY AN UNUSED PLACEHOLDER
                            }
                        ),
                        opts=ResourceOptions(parent=self),
                    )
                else:
                    new_to_process.append((stem, profile))
            if len(to_process_pipelines) == len(new_to_process):
                log.warn(
                    f"Unable to resolve all pipeline inheritances. The following"
                    f"pipelines are unavailable:"
                    f"{json.dumps(to_process_pipelines)}"
                )
                break
            else:
                to_process_pipelines = new_to_process


class WorkflowMetaRegistry(CapeComponentResource):
    """Class representing the workflow metadata registry.

    In CAPE, a workflow refers to an ApacheAirflow workflow (DAG). This registry
    is a mapping of workflow ids (`dag_id` for each DAG) to a listing of data
    analysis pipelines (DAPs) used by the workflow and their specific versions.

    The main use case for this registry is to have a way to query for a list of
    DAP@version entries for a workflow in order to determine which DAP profiles
    (mainly for `parameterSchema` information) are in use. As other metadata is
    identified as being needed, it will be added here.

    This resource only creates the infrastructure for workflow metadata. Workflows
    themselves are deployed outside the pulumi flow (in the cape-cod-env ansible
    repo).
    """

    @property
    def default_config(self) -> dict:
        """Implementation of abstract property `default_config`.

        Returns:
            The default config dict for the workflow registry.
            THIS COMPONENT HAS NOTHING CONFIGURABLE AT THIS TIME.
        """
        return {}

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:meta:capemeta:WorkflowMetaRegistry"

    def __init__(self, **kwargs):
        self.name = "cape-workflow-meta-registry"
        self.desc_name = kwargs.get("desc_name")
        super().__init__(self.name, **kwargs)

        self.create_workflow_meta_store()

    def create_workflow_meta_store(self):
        """Sets up a data store to hold airflow workflow metadata."""
        # setup a DynamoDB table to hold documents containing metadata on
        # airflow workflow metadata. keyed on unique workflow `dag_id`
        # NOTE: we can set up our Dynamo connections to go through a VPC
        #       endpoint instead of the way we're currently doing (using the
        #       fact that we have a NAT and egress requests to go through the
        #       boto3 dynamo client, which makes the requests go through the
        #       public internet). VPC endpoint is arguably more secure and
        #       performant as it's a direct connection to Dynamo from our
        #       clients, but it adds cost.

        self.workflow_meta_ddb_table = DynamoTable(
            name=f"{self.name}-WorkflowMetaStore",
            hash_key="dag_id",
            range_key=None,
            idx_attrs=[
                # NOTE: we do not need to define any part of the "schema" here
                #       that isn't needed in an index.
                {"name": "dag_id", "type": "S"},
            ],
            desc_name=(f"{self.desc_name} Workflow Metadata Table"),
            opts=ResourceOptions(parent=self),
        )
