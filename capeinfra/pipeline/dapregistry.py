"""Abstractions for data analysis pipeline registry."""

import json
from pathlib import Path

import pulumi_aws as aws
from boto3.dynamodb.types import TypeSerializer
from pulumi import Output, ResourceOptions, log

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
            hash_key="pipeline_name",
            range_key="version",
            attributes=[
                # NOTE: we do not need to define any part of the "schema" here
                #       that isn't needed in an index.
                {
                    "name": "pipeline_name",
                    "type": "S",
                },
                {
                    "name": "version",
                    "type": "S",
                },
            ],
            opts=ResourceOptions(parent=self),
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
                        range_key=self.analysis_pipeline_registry_ddb_table.range_key.apply(
                            lambda rk: f"{rk}"
                        ),
                        item=Output.json_dumps(
                            {
                                "pipeline_name": {"S": profile["pipelineName"]},
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
