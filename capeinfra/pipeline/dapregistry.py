"""Abstractions for data analysis pipeline registry."""

import json
from pathlib import Path

import pulumi_aws as aws
from pulumi import FileAsset, Output, ResourceOptions, log

from capeinfra.resources.objectstorage import VersionedBucket
from capeinfra.util.naming import disemvowel
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
            "dap-assets": "./assets/analysis-pipelines",
        }

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
        super().__init__(
            "capeinfra:pipeline:DAPRegistry", name, *args, **kwargs
        )

        self.name = f"{name}"
        self.dap_assets = Path(self.config["dap-assets"])

        self.create_dap_objstore()
        self.create_dap_registry_table()
        self.load_pipeline_assets()

    def create_dap_objstore(self):
        """Set up an analysis pipeline object store."""

        # bucket for hosting static web application
        self.dap_assets_bucket = VersionedBucket(
            f"{self.name}-assets-vbkt",
            bucket_name="cape-dap-assets",
            desc_name=(f"{self.desc_name} analysis pipeline assets bucket"),
            opts=ResourceOptions(parent=self),
        )

        # if we need bucket policies or anything, add them here

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
        dap_fixture_pth = self.dap_assets / self.DAP_FIXTURE

        # make sure we have a json file that defines all the deploy time
        # pipelines
        if not dap_fixture_pth.exists():
            log.warn(
                (
                    f"Unable to locate analysis pipeline fixtures file: "
                    f"{dap_fixture_pth}. No analysis pipelines will be "
                    f"deployed."
                ),
                self,
            )
            return

        # load up the json
        self.dap_fixtures = {}
        with open(dap_fixture_pth) as f:
            self.dap_fixtures = json.load(f)

        # pipeline spec file starts with an outer list of objects defining
        # pipeline types (e.g. nextflow). inner objects definie the pipelines
        # for the type
        for pipeline_type_spec in self.dap_fixtures:
            pltype = pipeline_type_spec.get("type", None)
            # TODO: for now we limit to nextflow pipelines explicitly. this will
            #       have to change eventually
            if pltype == "nextflow":
                # now iterate the pipelines for the type
                for pipeline in pipeline_type_spec.get("pipelines", None):
                    # and the versions for the pipeline
                    for version in pipeline.get("versions", []):
                        display_name = pipeline["display_name"]
                        pipeline_name = pipeline["pipeline_name"]
                        version_id = version["version"]
                        profile_root = pipeline["profile_root"]
                        # profile_id e.g. becomes 'bactopia' for profile root
                        # 'profiles/bactopia'
                        profile_id = profile_root.split("/")[-1]
                        profiles = version.get("profiles", [])

                        uploaded_profiles = []

                        # first upload the profiles for the (pipeline, version)
                        # so we can build a list of dicts of successful uploads
                        # to go into dynamodb
                        for profile in profiles:
                            objkey = (
                                f"{profile_id}/{version_id}/{profile['file']}"
                            )
                            prof_pth = (
                                self.dap_assets / profile_root / profile["file"]
                            )

                            self.dap_assets_bucket.add_object(
                                f"{profile_id}-{version_id}-{profile['file']}",
                                key=objkey,
                                source=FileAsset(prof_pth),
                            )

                            uploaded_profiles.append(
                                {
                                    "key": {"S": objkey},
                                    "display_name": {
                                        "S": profile["display_name"]
                                    },
                                }
                            )

                        # and create a dynamodb entry for the (pipeline, version)
                        aws.dynamodb.TableItem(
                            f"{self.name}-{disemvowel(display_name)}-{version_id}-ddbitem",
                            table_name=self.analysis_pipeline_registry_ddb_table.name,
                            hash_key=self.analysis_pipeline_registry_ddb_table.hash_key,
                            range_key=self.analysis_pipeline_registry_ddb_table.range_key.apply(
                                lambda rk: f"{rk}"
                            ),
                            item=Output.json_dumps(
                                {
                                    "display_name": {"S": display_name},
                                    "pipeline_name": {"S": pipeline_name},
                                    "version": {"S": version_id},
                                    "pipeline_type": {"S": "nextflow"},
                                    "nextflow_config": self.DEFAULT_NEXTFLOW_CONFIG,
                                    "profiles": {
                                        "L": [
                                            {
                                                "M": up
                                                for up in uploaded_profiles
                                            }
                                        ]
                                    },
                                }
                            ),
                            opts=ResourceOptions(parent=self),
                        )
