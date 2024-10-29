"""Resources for CAPE infra specific to the private swimlane.

This includes the private VPC, API/VPC endpoints and other top-level resources.
"""

import json
import os.path
import pathlib

import pulumi_aws as aws
from pulumi import (
    AssetArchive,
    Config,
    FileAsset,
    Output,
    ResourceOptions,
    warn,
)

from capeinfra.resources.loadbalancer import AppLoadBalancer

from ..iam import (
    get_bucket_reader_policy,
    get_bucket_web_host_policy,
    get_dap_api_policy,
    get_inline_role,
    get_instance_profile,
    get_nextflow_executor_policy,
    get_sqs_lambda_dap_submit_policy,
    get_sqs_lambda_glue_trigger_policy,
    get_sqs_notifier_policy,
    get_vpce_api_invoke_policy,
)

# TODO: ISSUE #145 This import is to support the temporary dap results s3
#       handling.
from ..pipeline.data import DataCrawler, EtlJob
from ..resources.certs import BYOCert
from ..resources.objectstorage import VersionedBucket
from ..swimlane import ScopedSwimlane
from ..util.config import CapeConfig
from ..util.file import file_as_string
from ..util.naming import disemvowel


class PrivateSwimlane(ScopedSwimlane):
    """Contains resources for the private swimlane of the CAPE Infra."""

    @property
    def default_config(self) -> dict:
        """Implementation of abstract property `default_config`.

        The default config has one public subnet only in the 10.0.0.0-255
        address space. There are no private subnets.

        Returns:
            The default config dict for this swimlane.
        """
        return {
            # by default (if not overridden in config) this will get ip space
            # 10.0.0.0-255
            "cidr-block": "10.0.0.0/24",
            "domain": "cape-dev.org",
            "public-subnet": {
                "cidr-block": "10.0.0.0/24",
            },
            "private-subnets": [],
            "static-apps": [],
            "api": {
                "dap": {
                    "meta": {
                        "stage-name": "dev",
                    },
                },
            },
            "compute": {},
            "vpn": {
                "cidr-block": "10.1.0.0/22",
                "transport-proto": "udp",
            },
        }

    def __init__(
        self, name, auto_assets_bucket: aws.s3.BucketV2, *args, **kwargs
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)
        # TODO: ISSUE #153 is there a better way to expose the auto assets
        #       bucket since we're now passing it to every client that needs a
        #       lambda script? Same for data catalog (which is passed to the
        #       swimlane base class)
        self.auto_assets_bucket = auto_assets_bucket

        aws_config = Config("aws")
        self.aws_region = aws_config.require("region")

        self.create_analysis_pipeline_registry()
        self.create_dap_submission_queue()
        # TODO: probably want to wrap all this up in the private api resources
        #       like deploying the static apps is in static resources
        self.create_dap_api()
        self.create_static_web_resources()
        self.create_private_api_resources()
        self._create_hosted_domain()
        self.create_vpn()
        self.prepare_nextflow_executor()
        self.create_dap_results_s3()

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

    def create_dap_api(self):
        """Create the data analysis pipeline API for the private swimlane."""

        # API resource itself
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

        # Role for the lambda handlers of the API.
        # NOTE: At this time we need one role for all possible operations of the
        #       API (e.g. if it needs to write to SQS in one function and read
        #       from DynamoDB in another, this role's policy must have both
        #       those grants). This may not be the long term implementation.
        self.api_lambda_role = get_inline_role(
            f"{self.basename}-dapapi-lmbd-role",
            f"{self.desc_name} data analysis pipeline lambda role",
            "lmbd",
            "lambda.amazonaws.com",
            Output.all(
                queue_name=self.dap_submit_queue.name,
                table_name=self.analysis_pipeline_registry_ddb_table.name,
            ).apply(lambda kwargs: get_dap_api_policy(**kwargs)),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )

        # NOTE: this is just till we get openapi specs working. Even if we don't
        #       go that route in the near term, this could use some refactor and
        #       hooking up to the pulumi config
        endpoint_specs = [
            {
                "name": "createpipeline",
                "handler": "index.index_handler",
                "runtime": "python3.11",
                "handler_src": (
                    "./assets/lambda/api-handlers/analysis-pipeline/"
                    "queue_analysis_pipeline_run.py"
                ),
                "handler_vars": {"DAP_QUEUE_NAME": self.dap_submit_queue.name},
                "path_part": "analysispipeline",
                "method": "POST",
                "enable_cors": True,
            },
            {
                "name": "listpipelines",
                "handler": "index.index_handler",
                "runtime": "python3.11",
                "handler_src": (
                    "./assets/lambda/api-handlers/analysis-pipeline/"
                    "list_analysis_pipelines.py"
                ),
                "handler_vars": {
                    "DAP_REG_DDB_TABLE": self.analysis_pipeline_registry_ddb_table.name
                },
                "path_part": "analysispipelines",
                "method": "GET",
                "enable_cors": True,
            },
            {
                "name": "listexecutors",
                "handler": "index.index_handler",
                "runtime": "python3.11",
                "handler_src": (
                    "./assets/lambda/api-handlers/analysis-pipeline/"
                    "list_pipeline_executors.py"
                ),
                "handler_vars": {},
                "path_part": "pipelineexecutors",
                "method": "GET",
                "enable_cors": True,
            },
        ]

        # tracks the methods and integrations we define below. without this
        # things were made in the wrong order.
        # NOTE: when working with api respurces/methods/integrations, it seems
        #       that we need to specify these dependencies explicitly or pulumi
        #       may try to make things before stuff they depend on are ready.
        #       though pulumi usually figures this kind of thing out pretty
        #       well, this case is mentioned in their docs as something you
        #       probably want to do.
        deployment_depends = []

        # iterate then endpoint specs and make the endpoints (resources) and
        # wire up the methods of interest. then add the integration (which in
        # this case is a lambda handler with perms needed to do its thing)
        for es in endpoint_specs:
            short_name = disemvowel(es["name"])
            handler_lambda = aws.lambda_.Function(
                f"{self.basename}-dapapi-{short_name}-lmbdfn",
                role=self.api_lambda_role.arn,
                handler=es["handler"],
                runtime=es["runtime"],
                code=AssetArchive({"index.py": FileAsset(es["handler_src"])}),
                environment={"variables": es["handler_vars"]},
                opts=ResourceOptions(parent=self),
            )

            # permission for rest api to invoke lambda
            aws.lambda_.Permission(
                f"{self.basename}-dapapi-{short_name}-allow-lmbd",
                action="lambda:InvokeFunction",
                function=handler_lambda.arn,
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
            handler_resource = aws.apigateway.Resource(
                f"{self.basename}-dapapi-{short_name}-rsrc",
                parent_id=self.dap_rest_api.root_resource_id,
                path_part=es["path_part"],
                rest_api=self.dap_rest_api.id,
                opts=ResourceOptions(parent=self),
            )

            handler_method = aws.apigateway.Method(
                f"{self.basename}-dapapi-{short_name}-{es['method']}-mthd",
                http_method=es["method"],
                # TODO: we need authz
                authorization="NONE",
                resource_id=handler_resource.id,
                rest_api=self.dap_rest_api.id,
                opts=ResourceOptions(parent=self),
            )

            handler_integration = aws.apigateway.Integration(
                f"{self.basename}-dapapi-{short_name}-{es['method']}-intg",
                http_method=handler_method.http_method,
                resource_id=handler_resource.id,
                rest_api=self.dap_rest_api.id,
                # NOTE: with lambda backed endpoints, integration http method
                #       should be POST
                integration_http_method="POST",
                type="AWS_PROXY",
                uri=handler_lambda.invoke_arn,
                opts=ResourceOptions(parent=self),
            )

            # TODO: ISSUE #141 this is probably not the best way to do this.
            #       given we'd like to refactor to using openapi specs anyway,
            #       not going to spend much time on it right now...
            if es["enable_cors"]:
                # If we are enabling CORS, we need:
                #   - an OPTIONS method handler
                #   - a method response for OPTIONS that forces the required
                #     CORS headers to be returned (with a 200 status)
                #   - a MOCK integration (with a json/200 request template)
                #   - an OPTIONS integration response that has the correct CORS
                #     headers
                options_method = aws.apigateway.Method(
                    f"{self.basename}-dapapi-{short_name}-options-mthd",
                    http_method="OPTIONS",
                    # TODO: we need authz
                    authorization="NONE",
                    resource_id=handler_resource.id,
                    rest_api=self.dap_rest_api.id,
                    opts=ResourceOptions(parent=self),
                )

                aws.apigateway.MethodResponse(
                    f"{self.basename}-dapapi-{short_name}-options-mthdrsp",
                    rest_api=self.dap_rest_api.id,
                    resource_id=handler_resource.id,
                    http_method=options_method.http_method,
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                    opts=ResourceOptions(
                        parent=self, depends_on=[options_method]
                    ),
                )

                opts_integration = aws.apigateway.Integration(
                    f"{self.basename}-dapapi-{short_name}-options-intg",
                    http_method=options_method.http_method,
                    type="MOCK",
                    resource_id=handler_resource.id,
                    rest_api=self.dap_rest_api.id,
                    request_templates={
                        "application/json": "{'statusCode':200}"
                    },
                    opts=ResourceOptions(
                        parent=self, depends_on=[options_method]
                    ),
                )

                aws.apigateway.IntegrationResponse(
                    f"{self.basename}-dapapi-{short_name}-options-intgrsp",
                    rest_api=self.dap_rest_api.id,
                    resource_id=handler_resource.id,
                    http_method=options_method.http_method,
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Headers": (
                            "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,"
                            "X-Amz-Security-Token'"
                        ),
                        "method.response.header.Access-Control-Allow-Methods": (
                            f"'OPTIONS,{es['method']}'"
                        ),
                        # TODO: ISSUE #141 we should not allow any origin here.
                        #       if we keep with this CORS stuff and the result
                        #       of an openapi setup is similar, we'll want a
                        #       config value for the origins we allow cross
                        #       requests from (or explicitly limit to whatever
                        #       to setting is for the swimlane's domain -
                        #       though that would lock use of the API to the
                        #       VPN for dev purposes)
                        "method.response.header.Access-Control-Allow-Origin": (
                            "'*'"
                        ),
                    },
                    opts=ResourceOptions(
                        parent=self, depends_on=[opts_integration]
                    ),
                )

            deployment_depends.extend([handler_method, handler_integration])

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
                # NOTE: not specifying these led to the deployment being
                #       constructed before things it depends on
                depends_on=deployment_depends,
            ),
        )

        # NOTE: our stage name suffix (e.g. `dev` vs `prod`) is in the config
        #       file, and if it is not defined we really want the deployment
        #       to fail. so we'll let the KeyError happen and not try to do
        #       anything about it
        # TODO:as we only have one api right now, we're storing the stage name
        #      explicitly. we will need this for a resource name later, which
        #      means we cannot use any Output property of the stage (i.e.
        #      stage_name, which is really what we want) due to pulumi
        #      limitations. What we really need to to move toward is a
        #      collection of apis (like we have for albs and such) with a name
        #      per entry in the collection.
        self.dap_api_stage_name = (
            f"dapapi-{self.config.get('api', 'dap', 'meta', 'stage-name')}"
        )

        # make a stage for the deployment manually.
        # NOTE: we could make this implicitly by just setting stage_name on the
        #       deployment resource, but there are warnings in the pulumi docs
        #       about weedy things that lead to deletion and addition of stages
        #       on redeployments if done this way, which ultimately leads to a
        #       service interruption.
        self.dap_api_deployment_stage = aws.apigateway.Stage(
            f"{self.basename}-dapapi-dplymntstg",
            stage_name=self.dap_api_stage_name,
            description=(
                f"CAPE data analysis pipeline API {self.dap_api_stage_name} "
                "deployment stage"
            ),
            deployment=self.dap_api_deployment.id,
            rest_api=self.dap_rest_api.id,
            # TODO: ISSUE #67
            opts=ResourceOptions(parent=self),
        )

    def create_analysis_pipeline_registry(self):
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

        # TODO: long term it is not tenable for us to have all the
        #       config stuff for all the pipeline frameworks
        #       specified in this manner. we should consider keeping
        #       the default config in common files or something
        #       like that and then point to the file in this table
        nextflow_config = {
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
                                "uploadStorageClass": {
                                    "S": "INTELLIGENT_TIERING"
                                },
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
        nextflow_pipelines = {
            "bactopia/bactopia": ["v3.0.1", "dev"],
        }
        for pipeline in nextflow_pipelines:
            for version in nextflow_pipelines[pipeline]:
                # TODO: we're hard coding this table for now. longer term we really
                #       probably want an initial canned setup (for initial deploy) and
                #       the ability to add these records at runtime so users can extend
                #       when they need to. right now we're only adding the bactopia
                #       tutorial as a pipeline
                # TODO: ISSUE #84
                aws.dynamodb.TableItem(
                    f"{self.basename}-{disemvowel(pipeline)}-{version}-ddbitem",
                    table_name=self.analysis_pipeline_registry_ddb_table.name,
                    hash_key=self.analysis_pipeline_registry_ddb_table.hash_key,
                    range_key=self.analysis_pipeline_registry_ddb_table.range_key.apply(
                        lambda rk: f"{rk}"
                    ),
                    item=Output.json_dumps(
                        {
                            "pipeline_name": {"S": pipeline},
                            "version": {"S": version},
                            "pipeline_type": {"S": "nextflow"},
                            "nextflow_config": nextflow_config,
                        }
                    ),
                    opts=ResourceOptions(parent=self),
                )

    def create_dap_submission_queue(self):
        """Creates and configures the SQS queue where DAP submissions will go.

        Configuration of this queue also involves configuring the Lambda that is
        triggered on messages being added to the queue.
        """
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

        # get a role for the raw bucket trigger
        self.dap_submit_sqs_trigger_role = get_inline_role(
            f"{self.basename}-dapq-sqstrgrole",
            f"{self.desc_name} DAP submission SQS trigger role",
            "lmbd",
            "lambda.amazonaws.com",
            Output.all(
                qname=self.dap_submit_queue.name,
                table_name=self.analysis_pipeline_registry_ddb_table.name,
            ).apply(
                lambda args: get_sqs_lambda_dap_submit_policy(
                    args["qname"], args["table_name"]
                )
            ),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        self.dap_submit_qmsg_handler = aws.lambda_.Function(
            f"{self.basename}-dapq-sqslmbdtrgfnct",
            role=self.dap_submit_sqs_trigger_role.arn,
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/sqs_dap_submit_lambda.py"
                    )
                }
            ),
            runtime="python3.11",
            timeout=30,
            # in this case, the zip file for the lambda deployment is
            # being created by this code. and the zip file will be
            # called index. so the handler must be start with `index`
            # and the actual function in the script must be named
            # the same as the value here
            handler="index.index_handler",
            environment={
                "variables": {
                    "DAP_REG_DDB_TABLE": self.analysis_pipeline_registry_ddb_table.name,
                    "DDB_REGION": self.aws_region,
                }
            },
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} DAP submission sqs message lambda trigger "
                    "function"
                )
            },
        )

        aws.lambda_.EventSourceMapping(
            f"{self.basename}-dapq-sqslmbdatrgr",
            event_source_arn=self.dap_submit_queue.arn,
            function_name=self.dap_submit_qmsg_handler.arn,
            function_response_types=["ReportBatchItemFailures"],
        )

    # TODO: ISSUE #126
    # TODO: refactor out elsewhere
    def _deploy_static_app(self, sa_cfg: CapeConfig):
        """Create the S3 bucket for a static app and then deploy app files.

        Args:
            sa_cfg: The configuration dict for the static application.
        """
        # Grab the config values of interest so we can check if we should
        # proceed
        sa_name = sa_cfg.get("name", default=None)
        sa_fqdn = sa_cfg.get("fqdn", default=None)
        sa_dir = sa_cfg.get("dir", default=None)
        sa_files = sa_cfg.get("files", default=[])
        tls_cfg = sa_cfg.get("tls", default=None)

        if None in (sa_name, sa_fqdn, sa_dir, sa_files, tls_cfg):
            msg = (
                f"Static App {sa_name or 'UNNAMED'} contains one or more "
                "invalid configuration values that are required. The "
                "application will not be deployed. Check the app name, fqdn, "
                "repo directory, app files and tls configuration."
            )

            warn(msg)
            raise ValueError(msg)

        # NOTE:
        # self.static_apps format:
        # {
        #   app_name: {
        #       "bucket": VersionedBucket,
        #       "cert": aws.acm.Certificate,
        #       "paths": [],
        #   }
        # }
        self.static_apps.setdefault(sa_name, {})

        # bucket for hosting static web application
        # TODO: ISSUE #127
        self.static_apps[sa_name]["bucket"] = VersionedBucket(
            f"{self.basename}-sa-{sa_name}-vbkt",
            bucket_name=sa_fqdn,
            desc_name=(
                f"{self.desc_name} analysis pipeline static web application "
                "bucket"
            ),
            opts=ResourceOptions(parent=self),
        )

        # bucket policy that allows read access to this bucket if you come from
        # the private swimlane vpc
        aws.s3.BucketPolicy(
            f"{self.basename}-{sa_name}-vbktplcy",
            bucket=self.static_apps[sa_name]["bucket"].bucket.id,
            policy=get_bucket_web_host_policy(
                self.static_apps[sa_name]["bucket"].bucket,
                self.static_app_vpcendpoint.id,
            ),
        )

        # deploy the static app files
        # TODO: ISSUE #128
        # TODO: this is not great long term as (much like etl scripts) we
        #       really don't want this site managed in this repo, nor do we want
        #       to re-upload these files on every deployment (as could happen
        #       here). but for now...
        for idx, f in enumerate(sa_files):
            # first we need to track the path to the file (but not the
            # filename). we need this to setup the ALB listener rules later.
            # TODO: ISSUE #128
            p = pathlib.Path(f["path"])
            self.static_apps[sa_name].setdefault("paths", set()).add(p.parent)

            # then actually add the file to the bucket
            # TODO: ISSUE #129
            self.static_apps[sa_name]["bucket"].add_object(
                f"{self.basename}-{sa_name}-{idx}",
                f["path"],
                source=FileAsset(os.path.join(sa_dir, f["path"])),
                content_type=f["content-type"],
            )

        # NOTE:not handling ecxeption that could be thrown here as we want the
        #      pulumi operation to fail in that case.
        self.static_apps[sa_name]["cert"] = BYOCert.from_config(
            f"{self.basename}-{sa_name}-byoc",
            tls_cfg,
            desc_name=f"BYOCert for {sa_name}",
        )

    def _create_static_app_alb(self):
        """Create the application load balancer for static applications."""

        self.create_alb(
            "static",
            [
                self.private_subnets["vpn"],
                self.private_subnets["vpn2"],
            ],
            self.static_apps["dap-ui"]["cert"].acmcert,
        )

        # attach the static app targets to the alb
        for sa_name, sa_info in self.static_apps.items():
            self.albs["static"].add_static_app_target(
                self.static_app_vpcendpoint,
                sa_name,
                sa_info["paths"],
                port=443,
                proto="HTTPS",
            )

    # TODO: very similar to _create_static_app_alb
    def _create_api_alb(self):
        """Create the application load balancer for private apis."""

        self.create_alb(
            "api",
            [
                self.private_subnets["vpn"],
                self.private_subnets["vpn2"],
            ],
            self.static_apps["dap-ui"]["cert"].acmcert,
        )

        # attach the api gateway targets to the alb
        self.albs["api"].add_api_target(
            self.api_vpcendpoint,
            self.dap_api_stage_name,
            self.dap_api_deployment_stage.id,
            port=443,
            proto="HTTPS",
        )
        # TODO: api gateway targets...
        # for sa_name, sa_info in self.static_apps.items():
        #     self.albs["static"].add_static_app_target(
        #         self.static_app_vpcendpoint,
        #         sa_name,
        #         sa_info["paths"],
        #         port=443,
        #         proto="HTTPS",
        #     )

    # TODO: ISSUES #128
    def create_static_web_resources(self):
        """Creates resources related to private swimlane web resources."""

        sa_cfgs = self.config.get("static-apps", default=None)
        if sa_cfgs is None:
            warn(f"No static apps configured for swimlane {self.basename}")
            return

        self.static_app_vpcendpoint = aws.ec2.VpcEndpoint(
            f"{self.basename}-sas3vpcep",
            vpc_id=self.vpc.id,
            service_name=f"com.amazonaws.{aws.get_region().name}.s3",
            vpc_endpoint_type="Interface",
            # TODO: ISSUE #131
            subnet_ids=[
                self.private_subnets["vpn"].id,
                self.private_subnets["vpn2"].id,
            ],
            # TODO: ISSUE #112
            tags={
                "desc_name": f"{self.desc_name} S3 webhost endpoint",
            },
        )

        self.static_apps = {}
        for sa_cfg in sa_cfgs:
            try:
                self._deploy_static_app(CapeConfig(sa_cfg))
            except ValueError:
                # ValueError will be thrown for invalid configuration of a
                # static app. Logging will have already happened, so we just
                # need to halt the deployment of that app and move on
                continue

        # Now that we have the static app buckets created, lock them down to
        # read only
        # TODO: ISSUE #134
        aws.ec2.VpcEndpointPolicy(
            f"{self.basename}-sas3vpcepplcy",
            vpc_endpoint_id=self.static_app_vpcendpoint.id,
            # TODO: ISSUE #135
            policy=Output.all(
                buckets=[
                    sa["bucket"].bucket.bucket
                    for sa in self.static_apps.values()
                ],
            ).apply(
                lambda args: get_bucket_reader_policy(
                    buckets=args["buckets"], principal="*"
                )
            ),
            opts=ResourceOptions(parent=self),
        )

        self._create_static_app_alb()

    # TODO: very similar to create_static_web_resources. DRY
    def create_private_api_resources(self):
        """Creates resources related to private swimlane apis."""

        # TODO: config for private apis

        # sa_cfgs = self.config.get("static-apps", default=None)
        # if sa_cfgs is None:
        #     warn(f"No static apps configured for swimlane {self.basename}")
        #     return

        # NOTE: our private DNS will send *all* api gateway traffic through
        #       this endpoint. at the time of this comment, this means we would
        #       not be able to route to public aws dns entries as those are
        #       only  available to public dns endpoints. if we ever end up need
        #       public (aws api gateway) apis as well, they will need something
        #       like a custom (public) domain name that we can route to instead
        self.api_vpcendpoint = aws.ec2.VpcEndpoint(
            f"{self.basename}-apivpcep",
            vpc_id=self.vpc.id,
            service_name=f"com.amazonaws.{aws.get_region().name}.execute-api",
            vpc_endpoint_type="Interface",
            private_dns_enabled=True,
            # TODO: ISSUE #131
            subnet_ids=[
                self.private_subnets["vpn"].id,
                self.private_subnets["vpn2"].id,
            ],
            # TODO: ISSUE #112
            tags={
                "desc_name": f"{self.desc_name} private api VPC endpoint",
            },
        )

        # self.static_apps = {}
        # for sa_cfg in sa_cfgs:
        #     try:
        #         self._deploy_static_app(CapeConfig(sa_cfg))
        #     except ValueError:
        #         # ValueError will be thrown for invalid configuration of a
        #         # static app. Logging will have already happened, so we just
        #         # need to halt the deployment of that app and move on
        #         continue

        # TODO: Need endpoint policy for api endpoints. Should include limit to
        #       this VPC only

        aws.ec2.VpcEndpointPolicy(
            f"{self.basename}-api-vpcepplcy",
            vpc_endpoint_id=self.api_vpcendpoint.id,
            # TODO: ISSUE #135
            policy=get_vpce_api_invoke_policy(self.api_vpcendpoint.id),
            opts=ResourceOptions(parent=self),
        )

        self._create_api_alb()

    def _create_hosted_domain(self):
        """Create the private zone for the swimlane.

        This must be done after setting up the ALB.
        """
        # private route53 zone
        rte53_prvt_zone_name = self.config.get("domain", default=None)

        # setup the private hosted zone. this is totally inside our private
        # vpc, so it doesn't need to be registered anywhere public unless used
        # for public facing resources as well.
        self.create_hosted_domain(rte53_prvt_zone_name)

        # we need a zone record per static app bucket
        for sa_name, sa_info in self.static_apps.items():
            self.create_private_domain_alb_record(
                sa_info["bucket"].bucket.bucket, sa_name, "static"
            )

        # and DNS for the zone
        self.create_private_hosted_dns(
            [self.private_subnets["vpn"], self.private_subnets["vpn2"]]
        )

    # TODO: ISSUE #100
    # TODO: ISSUE #130
    def create_vpn(self):
        """Creates/configures a Client VPN Endpoint for the private swimlane.

        In the case that the required configuration for the VPN ACM certificate
        does not exist or has issues, a message will be printed to the pulumi
        console and VPN configuration will cease.

        """

        try:
            tls_cfg = self.config.get("vpn", "tls")
            # NOTE: not handling exceptions possible here as we want pulumi
            #       operations to fail in that case
            self.vpn_byocert = BYOCert.from_config(
                f"{self.basename}-vpn-byoc",
                tls_cfg,
                desc_name=f"CAPE Private Swimlane VPN ACM BYOCert",
            )
        except ValueError as ve:
            warn(
                f"Error encountered in configuration of Private swimlane VPN. "
                f"{ve}. VPN will not be configured."
            )
            return

        # log group and log stream for the VPN endpoint
        self.vpn_log_group = aws.cloudwatch.LogGroup(
            f"{self.basename}-vpn-logs",
            name=f"{self.basename}-vpn-logs",
            tags={"desc_name": (f"{self.desc_name} VPN Log Group")},
            opts=ResourceOptions(parent=self),
        )

        self.vpn_log_stream = aws.cloudwatch.LogStream(
            f"{self.basename}-vpn-logs-stream",
            name=f"{self.basename}-vpn-logs-stream",
            log_group_name=self.vpn_log_group.name,
            opts=ResourceOptions(parent=self),
        )

        # Client VPN endpoint, which is the interface VPN connections go thu
        self.client_vpn_endpoint = aws.ec2clientvpn.Endpoint(
            f"{self.basename}-vpnep",
            description=f"{self.desc_name} Client VPN Endpoint",
            server_certificate_arn=self.vpn_byocert.acmcert.arn,
            authentication_options=[
                {
                    "type": "certificate-authentication",
                    "root_certificate_chain_arn": self.vpn_byocert.acmcert.arn,
                }
            ],
            client_cidr_block=self.config.get("vpn", "cidr-block"),
            connection_log_options={
                "enabled": True,
                "cloudwatch_log_group": self.vpn_log_group.name,
                "cloudwatch_log_stream": self.vpn_log_stream.name,
            },
            dns_servers=Output.all(
                ipaddrs=self.rte53_dns_ep.ip_addresses
            ).apply(
                lambda args: [ia["ip"] for ia in args["ipaddrs"]],
            ),
            tags={
                "desc_name": (
                    f"{self.desc_name} DAP submission sqs message lambda trigger "
                    "function"
                )
            },
            transport_protocol=self.config.get("vpn", "transport-proto"),
            opts=ResourceOptions(parent=self),
        )

        # The client endpoint needs to be associated with a subnet, so associate
        # it with the configured "vpn" subnet.
        # TODO: ISSUE #100
        subnet_association = aws.ec2clientvpn.NetworkAssociation(
            f"{self.basename}-vpnassctn",
            client_vpn_endpoint_id=self.client_vpn_endpoint.id,
            subnet_id=self.private_subnets["vpn"].id,
            opts=ResourceOptions(
                depends_on=[self.client_vpn_endpoint],
                parent=self.client_vpn_endpoint,
            ),
        )

        # By default, the client endpoint will get a route to the VPC itself. we
        # need to also authorize the endpoint to route traffic to the VPN subnet
        # and to the internet (through the VPN subnet). This requires an auth
        # rule and a route for the internet case and just an auth rule for the
        # VPN case

        # NOTE: leaving as 2 explicit auth rule creations instead of
        # trying to reduce DRY violation in a loop or something on purpose. Do
        # not know how this is going to shake out in the long term and we may
        # end up with more/fewer rules. :shrug: we can refactor when that
        # becomes clear

        auth_rule_vpn = aws.ec2clientvpn.AuthorizationRule(
            f"{self.basename}-vpn-authzrl",
            client_vpn_endpoint_id=self.client_vpn_endpoint.id,
            # access vpn subnet only
            target_network_cidr=(
                self.private_subnets["vpn"].cidr_block.apply(lambda cb: f"{cb}")
            ),
            # access whole vpc
            # target_network_cidr=(self.vpc.cidr_block.apply(lambda cb: f"{cb}")),
            # TODO: ISSUE #101
            authorize_all_groups=True,
            opts=ResourceOptions(parent=self.client_vpn_endpoint),
        )

        auth_rule_inet = aws.ec2clientvpn.AuthorizationRule(
            f"{self.basename}-inet-authzrl",
            client_vpn_endpoint_id=self.client_vpn_endpoint.id,
            # access vpn subnet only
            target_network_cidr="0.0.0.0/0",
            # access whole vpc
            # target_network_cidr=(self.vpc.cidr_block.apply(lambda cb: f"{cb}")),
            # TODO: ISSUE #101
            authorize_all_groups=True,
            opts=ResourceOptions(parent=self.client_vpn_endpoint),
        )

        # Route to internet (egress only)
        aws.ec2clientvpn.Route(
            f"{self.basename}-inet-rt",
            client_vpn_endpoint_id=self.client_vpn_endpoint.id,
            destination_cidr_block="0.0.0.0/0",
            target_vpc_subnet_id=self.private_subnets["vpn"].id,
            opts=ResourceOptions(
                depends_on=[subnet_association, auth_rule_inet]
            ),
        )

    # TODO: ISSUE #115
    # Generalize this to work for all "head node"/"job submission"-like EC2
    # instances that spin up AWS Batch jobs. Currently it's very specific to
    # Nextflow and the policy it requires
    def prepare_nextflow_executor(self):
        """Creates necessary resources for our nextflow EC2 instance."""

        self.nextflow_role = get_inline_role(
            f"{self.basename}-nxtflw",
            f"{self.desc_name} instance role for nextflow kickoff instance",
            "ec2",
            "ec2.amazonaws.com",
            role_policy=get_nextflow_executor_policy(),
        )
        aws.iam.RolePolicyAttachment(
            f"{self.basename}-instnc-ssmvcroleatch",
            role=self.nextflow_role.name,
            policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
            opts=ResourceOptions(parent=self),
        )
        self.nextflow_role_profile = get_instance_profile(
            f"{self.basename}-nxtflw-instnc-rl", self.nextflow_role
        )

        for env_name in self.compute_environments:
            compute_environment = self.compute_environments[env_name]
            compute_environment.instance_role.arn
            aws.iam.RolePolicy(
                f"{self.basename}-nxtflow-pass-{env_name}-plcy",
                role=self.nextflow_role.id,
                policy=compute_environment.instance_role.arn.apply(
                    lambda arn: json.dumps(
                        {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "iam:PassRole",
                                    "Resource": arn,
                                }
                            ],
                        }
                    )
                ),
            )

    # TODO: ISSUE #144
    def create_dap_results_s3(self):
        """Create an S3 bucket for the data analysis pipeline results.

        This method also creates and ETL and crawler for the bucket.

        NOTE: This is a temporary implementation. We do not intend for this to
              remain in this format as it's very copy/paste from the tributary
              setup.
        """

        # NOTE: not adding any of this to the config till we know how we want to
        #       handle results/output s3 longer term in ISSUE #145
        short_name = disemvowel("dapresults")
        crawler_cfg = {
            "classifiers": ["cape-csv-standard-classifier"],
        }
        etl_cfg = {
            "name": "dap_results",
            "script": "glue/etl/etl_bactopia_results.py",
            # TODO: in the case of tributary ETL jobs, the prefix is added to
            #       the dynamo table item for the xform and then is used
            #       manually in the ETL script itself (due to difficulty having
            #       different jobs run for different overlapping prefixes in
            #       aws). in this case we're going to add it to the bucket
            #       notification because we only have one etl for pipeline
            #       output at this point and we only want the notifications in
            #       that prefix. this will not work long term (if we have one
            #       output location for all pipelines, which probably isn't a
            #       good idea anyway). Regardless of what we do, the different
            #       usages of prefix seems complicated and inconsistent.
            "prefix": "pipeline-output/bactopia-runs",
            "suffixes": ["tsv"],
            # NOTE: no additional pythonmodules at this point
        }

        base_bucket_name = f"{self.basename}-{short_name}"
        raw_bucket_name = f"{base_bucket_name}-raw-vbkt"
        self.raw_dap_results_bucket = VersionedBucket(
            raw_bucket_name,
            desc_name=f"{self.desc_name} Temporary DAP Results Raw Output Bucket",
            opts=ResourceOptions(parent=self),
        )
        clean_bucket_name = f"{base_bucket_name}-clean-vbkt"
        self.clean_dap_results_bucket = VersionedBucket(
            clean_bucket_name,
            desc_name=f"{self.desc_name} Temporary DAP Results Clean Output Bucket",
            opts=ResourceOptions(parent=self),
        )

        if self.data_catalog is not None:
            DataCrawler(
                f"{clean_bucket_name}-crwl",
                self.clean_dap_results_bucket.bucket,
                self.data_catalog.catalog_database,
                opts=ResourceOptions(parent=self),
                desc_name=(
                    f"{self.desc_name} Temporary DAP Results data crawler"
                ),
                config=crawler_cfg,
            )

        # this queue is where all notifications of new objects added to the
        # temporary DAP results bucket will go
        self.dap_results_data_queue = aws.sqs.Queue(
            # TODO: ISSUE #68
            f"{self.basename}-daprsltsq",
            name=f"{self.basename}-daprsltsq.fifo",
            content_based_deduplication=True,
            fifo_queue=True,
            tags={
                "desc_name": (
                    f"{self.desc_name} Temporary DAP results data "
                    "notification queue"
                )
            },
        )

        # setup ETL job for the DAP results
        # NOTE: depending how we implement results handling, we may need to add
        #       a dynamo abstraction like we have for raw data ETLs. If we have
        #       a single ETL per pipeline and we tie the results s3 buckets to
        #       pipelines, we probably wouldn't need that.
        dap_results_etl_job = EtlJob(
            f"{self.basename}-ETL-{short_name}",
            self.raw_dap_results_bucket.bucket,
            self.clean_dap_results_bucket.bucket,
            self.auto_assets_bucket,
            opts=ResourceOptions(parent=self),
            desc_name=(f"{self.desc_name} DAP results ETL job"),
            config=etl_cfg,
        )

        # Lambda SQS Target setup
        self.sqs_dap_results_trigger_role = get_inline_role(
            f"{self.basename}-{short_name}-sqstrgrole",
            f"{self.desc_name} Temporary DAP results data SQS trigger role",
            "lmbd",
            "lambda.amazonaws.com",
            Output.all(
                qname=self.dap_results_data_queue.name,
                job_names=[dap_results_etl_job.job.name],
            ).apply(
                lambda args: get_sqs_lambda_glue_trigger_policy(
                    args["qname"], args["job_names"]
                )
            ),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        self.dap_results_qmsg_handler = aws.lambda_.Function(
            f"{self.basename}-{short_name}-sqslmbdtrgfnct",
            role=self.sqs_dap_results_trigger_role.arn,
            code=AssetArchive(
                {
                    # TODO: ISSUE #150 this script is usable as is for any glue
                    #       job sqs handler, with the caveat that the glue job
                    #       has to support a RAW_BUCKET_NAME and ALERT_OBJ_KEY
                    #       env var (and the same sqs message format). it might
                    #       be worth changing the job spec to take a
                    #       `SRC_BUCKET_NAME` instead of `RAW` since not all
                    #       sources will be really raw data.
                    "index.py": FileAsset(
                        "./assets/lambda/sqs_etl_job_trigger_lambda.py"
                    )
                }
            ),
            runtime="python3.11",
            # in this case, the zip file for the lambda deployment is
            # being created by this code. and the zip file will be
            # called index. so the handler must be start with `index`
            # and the actual function in the script must be named
            # the same as the value here
            handler="index.index_handler",
            environment={
                "variables": {
                    "QUEUE_NAME": self.dap_results_data_queue.name,
                }
            },
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} Temporary DAP results sqs message "
                    "lambda trigger function"
                )
            },
        )

        aws.lambda_.EventSourceMapping(
            f"{self.basename}-{short_name}-sqslmbdatrgr",
            event_source_arn=self.dap_results_data_queue.arn,
            function_name=self.dap_results_qmsg_handler.arn,
            function_response_types=["ReportBatchItemFailures"],
        )

        # Bucket notification setup
        # get a role for the raw bucket trigger
        self.dap_results_bucket_trigger_role = get_inline_role(
            f"{self.basename}-{short_name}-s3trgrole",
            f"{self.desc_name} Temporary DAP Results data S3 bucket trigger role",
            "lmbd",
            "lambda.amazonaws.com",
            Output.all(
                qname=self.dap_results_data_queue.name,
            ).apply(lambda args: get_sqs_notifier_policy(args["qname"])),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=ResourceOptions(parent=self),
        )

        # Create our Lambda function that triggers the given glue job
        new_object_handler = aws.lambda_.Function(
            f"{self.basename}-{short_name}-lmbdtrgfnct",
            role=self.dap_results_bucket_trigger_role.arn,
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/new_dap_results_queue_notifier_lambda.py"
                    )
                }
            ),
            runtime="python3.11",
            # in this case, the zip file for the lambda deployment is
            # being created by this code. and the zip file will be
            # called index. so the handler must be start with `index`
            # and the actual function in the script must be named
            # the same as the value here
            handler="index.index_handler",
            environment={
                "variables": {
                    "QUEUE_NAME": self.dap_results_data_queue.name,
                    "ETL_JOB_ID": dap_results_etl_job.job.name,
                }
            },
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} Temporary DAP Results data lambda "
                    "trigger function"
                )
            },
        )

        # Give our function permission to invoke
        new_obj_handler_permission = aws.lambda_.Permission(
            f"{self.basename}-{short_name}S3-allow-lmbd",
            action="lambda:InvokeFunction",
            function=new_object_handler.arn,
            principal="s3.amazonaws.com",
            source_arn=self.raw_dap_results_bucket.bucket.arn,
            opts=ResourceOptions(parent=self),
        )

        aws.s3.BucketNotification(
            f"{self.basename}-{short_name}-s3ntfn",
            bucket=self.raw_dap_results_bucket.bucket.id,
            lambda_functions=[
                aws.s3.BucketNotificationLambdaFunctionArgs(
                    events=["s3:ObjectCreated:*"],
                    lambda_function_arn=new_object_handler.arn,
                    # TODO: ISSUE #144 This filter will be affected by how we do
                    #       this long term. We can filter one prefix, so for now
                    #       all pipelines should write output to sub-prefixes
                    #       under `pipeline-output/`
                    filter_prefix=f"{dap_results_etl_job.config['prefix']}/",
                    filter_suffix=f".{sfx}",
                )
                for sfx in dap_results_etl_job.config["suffixes"]
            ],
            opts=ResourceOptions(
                depends_on=[new_obj_handler_permission], parent=self
            ),
        )
