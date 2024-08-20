"""Resources for CAPE infra specific to the private swimlane.

This includes the private VPC, API/VPC endpoints and other top-level resources.
"""

import pulumi_aws as aws
from pulumi import AssetArchive, FileAsset, Output, ResourceOptions

from ..iam import get_dap_api_policy, get_inline_role
from ..swimlane import ScopedSwimlane
from ..util.naming import disemvowel


class PrivateSwimlane(ScopedSwimlane):
    """Contains resources for the private swimlane of the CAPE Infra."""

    def __init__(self, name, *args, **kwargs):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)

        # this queue is where all data analysis pipeline submission messages
        # will go
        self.dap_submit_queue = aws.sqs.Queue(
            # TODO: ISSUE #68
            f"{self.basename}-dapq",
            name=f"{self.basename}-dapq.fifo",
            content_based_deduplication=True,
            fifo_queue=True,
            tags={
                "desc_name": (
                    f"{self.desc_name} data analysis pipeline submission queue"
                )
            },
        )

        self.create_dap_api()
        self.create_analysis_pipeline_registry()

    @property
    def type_name(self) -> str:
        """Implementation of abstract property `type_name`.

        Returns:
            The type name (pulumi namespacing) for the resource.
        """
        return "capeinfra:swimlanes:PrivateSwimlane"

    @property
    def scope(self) -> str:
        """Implementation of abstract property `scope`.

        Returns:
            The scope (public, protected, private) of the swimlane.
        """
        return "private"

    @property
    def default_cfg(self) -> dict:
        """Implementation of abstract property `default_cfg`.

        The default config has one public subnet only in the 10.0.0.0-255
        address space. There are no private subnets.

        Returns:
            The default config dict for this swimlane.
        """
        return {
            # by default (if not overridden in config) this will get ip space
            # 10.0.0.0-255
            "cidr-block": "10.0.0.0/24",
            "public-subnet": {
                "cidr-block": "10.0.0.0/24",
            },
            "private-subnets": [],
        }

    def create_dap_api(self):
        """Create the data analysis pipeline API for the private swimlane."""

        self.api_lambda_role = get_inline_role(
            f"{self.basename}-dapapi-lmbd-role",
            f"{self.desc_name} data analysis pipeline lambda role",
            "lmbd",
            "lambda.amazonaws.com",
            self.dap_submit_queue.name.apply(
                lambda name: get_dap_api_policy(f"{name}")
            ),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )

        post_new_dap_lambda = aws.lambda_.Function(
            f"{self.basename}-dapapi-{disemvowel('createpipeline')}-lmbdfn",
            role=self.api_lambda_role.arn,
            handler="index.index_handler",
            runtime="python3.11",
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/api-handlers/analysis-pipeline/"
                        "queue_analysis_pipeline_run.py"
                    )
                }
            ),
            environment={
                "variables": {
                    "DAP_QUEUE_NAME": self.dap_submit_queue.name,
                }
            },
            opts=ResourceOptions(parent=self),
        )

        self.dap_rest_api = aws.apigateway.RestApi(
            f"{self.basename}-dapapi",
            description="CAPE Data Analysis Pipeline API",
            # TODO: ISSUE #61
            # NOTE: no pulumi Asset/Archive stuff here. we need the contents as
            #       a string.
            # body=Path(
            #    "./assets/api/analysis-pipeline/dap-api-spec.yaml"
            # ).read_text(),
            opts=ResourceOptions(parent=self),
        )

        # permission for rest api to invoke lambda
        aws.lambda_.Permission(
            f"{self.basename}-dapapi-{disemvowel('createpipeline')}-allow-lmbd",
            action="lambda:InvokeFunction",
            function=post_new_dap_lambda.arn,
            principal="apigateway.amazonaws.com",
            source_arn=self.dap_rest_api.execution_arn.apply(
                # NOTE: this allows lambda on all endpoints and all methods for
                #       the api. may not be a great idea. or we may want
                #       different permissions for different parts of the API.
                #       not sure till we have a really fleshed out API.
                lambda arn: f"{arn}/*/*"
            ),
            opts=ResourceOptions(parent=self),
        )

        # TODO: ISSUE #61 - START manual route/integration (TO BE REMOVED)
        post_new_dap_resource = aws.apigateway.Resource(
            f"{self.basename}-dapapi-{disemvowel('createpipeline')}-rsrc",
            parent_id=self.dap_rest_api.root_resource_id,
            path_part="analysispipeline",
            rest_api=self.dap_rest_api.id,
            opts=ResourceOptions(parent=self),
        )

        post_new_dap_method = aws.apigateway.Method(
            f"{self.basename}-dapapi-{disemvowel('createpipeline')}-mthd",
            http_method="POST",
            # TODO: we need authz
            authorization="NONE",
            resource_id=post_new_dap_resource.id,
            rest_api=self.dap_rest_api.id,
            opts=ResourceOptions(parent=self),
        )

        post_new_dap_integration = aws.apigateway.Integration(
            f"{self.basename}-dapapi-{disemvowel('createpipeline')}-intg",
            http_method=post_new_dap_method.http_method,
            resource_id=post_new_dap_resource.id,
            rest_api=self.dap_rest_api.id,
            integration_http_method="POST",
            type="AWS_PROXY",
            uri=post_new_dap_lambda.invoke_arn,
            opts=ResourceOptions(parent=self),
        )

        # TODO: ISSUE 61 - END manual route/integration (TO BE REMOVED)

        # Deployments and stages are needed to make APIs accessible. Another
        # reason we may wanna go with an API class to manage all of this in one
        # place
        self.dap_api_deployment = aws.apigateway.Deployment(
            f"{self.basename}-dapapi-dplymnt",
            rest_api=self.dap_rest_api.id,
            # TODO: ISSUE #65
            opts=ResourceOptions(
                parent=self,
                # NOTE: not specying these led to the deployment being
                #       constructed before things it depends on
                depends_on=[post_new_dap_method, post_new_dap_integration],
            ),
        )

        # make a stage for the deployment manually.
        # NOTE: we could make this implicitly by just setting stage_name on the
        #       deployment resource, but there are warnings in the pulumi docs
        #       about weedy things that lead to deletion and addition of stages
        #       on redeployments if done this way, which ultimately leads to a
        #       service interruption.
        # TODO: ISSUE #66
        stage_name = "dev"
        self.dap_api_deployment_stage = aws.apigateway.Stage(
            f"{self.basename}-dapapi-dplymntstg",
            stage_name=stage_name,
            description=(
                f"CAPE data analysis pipeline API {stage_name} deployment "
                "stage"
            ),
            deployment=self.dap_api_deployment.id,
            rest_api=self.dap_rest_api.id,
            # TODO: ISSUE #67
            opts=ResourceOptions(parent=self),
        )

    def create_analysis_pipeline_registry(
        self,
    ):
        """Sets up an analysis pipeline registry database.

        Args:
        """
        # setup a DynamoDB table to hold a mapping of pipeline names (user
        # facing names) to various config info for the running of the analysis
        # pipelines. E.g. a nextflow pipeline may have a default nextflow config
        # in the value object of its entry whereas a snakemake pipeline may have
        # a default snakemake config.
        # NOTE: DynamoDB stuff lives outside a VPC and is managed by AWS. This
        #       is in the private swimlane as it fits there logically. we may
        #       want to consider moving all AWS managed items into CapeMeta
        #       eventually.
        # NOTE: we can set up our Dynamo connections to go through a VPC
        #       endpoint instead of the way we're currently doing (using the
        #       fact that we have a NAT and egress requests to go through the
        #       boto3 dynamo client, which makes the requests go through the
        #       public internet). This is arguably more secure and performant as
        #       it's a direct connection to Dynamo from our clients.
        self.analysis_pipeline_registry_ddb_table = aws.dynamodb.Table(
            f"{self.basename}-anlysppln-rgstry-ddb",
            name=f"{self.basename}-AnalysisPipelineRegistry",
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

        # TODO: we're hard coding this table for now. longer term we really
        #       probably want an initial canned setup (for initial deploy) and
        #       the ability to add these records at runtime so users can extend
        #       when they need to. right now we're only adding the bactopia
        #       tutorial as a pipeline
        bactopia_version = "3.0.1"
        aws.dynamodb.TableItem(
            f"{self.basename}-bactp-ttrl-ddbitem",
            table_name=self.analysis_pipeline_registry_ddb_table.name,
            hash_key=self.analysis_pipeline_registry_ddb_table.hash_key,
            range_key=self.analysis_pipeline_registry_ddb_table.range_key.apply(
                lambda rk: f"{rk}"
            ),
            item=Output.json_dumps(
                {
                    "pipeline_name": {
                        "S": (
                            f"bactopia {bactopia_version} tutorial analysis"
                            "pipeline"
                        ),
                    },
                    "version": {"S": f"{bactopia_version}"},
                    "pipeline_type": {"S": "nextflow"},
                    # TODO: long term it is not tenable for us to have all the
                    #       config stuff for all the pipeline frameworks
                    #       specified in this manner. we should consider keeping
                    #       the default config in common files or something
                    #       like that and then point to the file in this table
                    "nextflow_config": {
                        "M": {
                            "aws": {
                                "M": {
                                    "accessKey": {"S": "<YOUR S3 ACCESS KEY>"},
                                    "secretKey": {"S": "<YOUR S3 SECRET KEY>"},
                                    "region": {"S": "us-east-2"},
                                    "client": {
                                        "M": {
                                            "maxConnections": {"N": 20},
                                            "connectionTimeout": {"N": 10000},
                                            "uploadStorageClass": {
                                                "S": "INTELLIGENT_TIERING"
                                            },
                                            "storageEncryption": {
                                                "S": "AES256"
                                            },
                                        }
                                    },
                                    "batch": {
                                        "M": {
                                            "cliPath": {"S": "/usr/bin/aws"},
                                            "maxTransferAttempts": {"N": 3},
                                            "delayBetweenAttempts": {
                                                "S": "5 sec"
                                            },
                                        }
                                    },
                                }
                            }
                        }
                    },
                }
            ),
            opts=ResourceOptions(parent=self),
        )
