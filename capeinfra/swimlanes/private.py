"""Resources for CAPE infra specific to the private swimlane.

This includes the private VPC, API/VPC endpoints and other top-level resources.
"""

import json
import os.path

import pulumi_aws as aws
from pulumi import (
    AssetArchive,
    Config,
    FileAsset,
    Output,
    ResourceOptions,
    warn,
)

from ..iam import (
    get_bucket_web_host_policy,
    get_dap_api_policy,
    get_inline_role,
    get_instance_profile,
    get_nextflow_executor_policy,
    get_sqs_lambda_dap_submit_policy,
)
from ..objectstorage import VersionedBucket
from ..swimlane import ScopedSwimlane
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
            "public-subnet": {
                "cidr-block": "10.0.0.0/24",
            },
            "private-subnets": [],
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

    def __init__(self, name, *args, **kwargs):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)

        aws_config = Config("aws")
        self.aws_region = aws_config.require("region")

        self.create_analysis_pipeline_registry()
        self.create_dap_submission_queue()
        self.create_dap_api()
        self.create_web_resources()
        self.create_vpn()
        self.prepare_nextflow_executor()

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
                # NOTE: not specifying these led to the deployment being
                #       constructed before things it depends on
                depends_on=[post_new_dap_method, post_new_dap_integration],
            ),
        )

        # NOTE: our stage name is in the config file, and if it is not defined
        #       we rally want the deployment to fail. so we'll let the KeyError
        #       happen and not try to do anything about it
        stage_name = self.config.get("api", "dap", "meta", "stage-name")

        # make a stage for the deployment manually.
        # NOTE: we could make this implicitly by just setting stage_name on the
        #       deployment resource, but there are warnings in the pulumi docs
        #       about weedy things that lead to deletion and addition of stages
        #       on redeployments if done this way, which ultimately leads to a
        #       service interruption.
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
        # TODO: ISSUE #84
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
                                            "maxConnections": {"N": "20"},
                                            "connectionTimeout": {"N": "10000"},
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
                                            "maxTransferAttempts": {"N": "3"},
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

    def create_web_resources(self):
        """"""
        # NOTE: This is a notional proof of concept. this is not intended to be
        #       a very maintainable or modifyable implementation. once we show
        #       it to be working and that it will fulfill the intended purpose
        #       for other use cases, we can make it better. we should probably
        #       abstract the ALB and "application" out to a separate class that
        #       can be instantiated a number of times based on config

        # TODO: Config all these values
        # need to make a new cert/key pair for this domain (wildcard cert?)
        bucket_name = "analysis-pipelines.cape-dev.org"

        # bucket for hosting static web application for analysis pipelines
        self.dap_web_assets_bucket = VersionedBucket(
            f"{self.basename}-dap-web-vbkt",
            bucket_name=bucket_name,
            desc_name=(
                f"{self.desc_name} analysis pipeline static web application "
                "bucket"
            ),
            opts=ResourceOptions(parent=self),
        )

        # bucket policy that allows read access to this bucket if you come from
        # the private swimlane vpc
        aws.s3.BucketPolicy(
            f"{self.basename}-dap-web-vbktplcy",
            bucket=self.dap_web_assets_bucket.bucket.id,
            policy=get_bucket_web_host_policy(
                self.dap_web_assets_bucket.bucket, self.vpc.id
            ),
        )

        # s3 endpoint for vpc
        self.dap_web_assets_s3vpcep = aws.ec2.VpcEndpoint(
            f"{self.basename}-dap-web-s3vpcep",
            vpc_id=self.vpc.id,
            service_name=f"com.amazonaws.{aws.get_region().name}.s3",
            vpc_endpoint_type="Interface",
            # TODO: need the second AZ vpn subnet here...
            subnet_ids=[self.private_subnets["vpn"].id],
            # TODO: ISSUE #112
            # TODO: make function, tighten s3 perms to GetObj if possible
            policy=Output.all(self.dap_web_assets_bucket.bucket).apply(
                lambda bucket_name: f"""{{
                "Version": "2012-10-17",
                "Statement": [{{
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:*"],
                    "Resource": [
                        "arn:aws:s3:::{bucket_name}",
                        "arn:aws:s3:::{bucket_name}/*"
                    ]
                }}]
            }}"""
            ),
        )

        # TODO: LEFTOFF
        # * new acm cert
        # * ALB
        # * Add route53 Stuff after VPC and subnets, but *before* client VPN
        #   * zone
        #   * zone records
        #   * resolver
        # * mod client vpn to use DNS (resolver ips)
        pass

    # TODO:ISSUE #99
    def create_vpn_acm_certificate(self):
        """Create an ACM Certificate resource for VPN.

        In the case that the VPN configuration section does not exist or has any
        missing values, a ValueError will be raised, meaning VPN configuration
        should not continue.

        Raises:
            ValueError: On missing/invalid configuration options
        """

        def read_pem(pth):
            """Simple file read helper for use in a list comprehension.

            This is used to read PEM files, but obvi the format of the file
            doesn't matter to `open`.

            Args:
                pth: the path to the file to read
            Raises:
                FileNotFoundError: if the path cannot be found.
            Returns:
                The contents of the file at `pth`.
            """
            s = None
            with open(pth) as f:
                s = f.read()

            return s

        tls = self.config.get("vpn", "tls")
        tls_dir = tls.get("dir")
        if tls_dir is None:
            raise ValueError(
                "TLS assets directory not configured for Private swimlane VPN."
            )

        try:
            ca_crt_pem, server_key_pem, server_cert_pem = [
                read_pem(os.path.join(tls_dir, f))
                for f in [
                    tls.get("ca-cert"),
                    tls.get("server-key"),
                    tls.get("server-cert"),
                ]
            ]

            self.vpn_server_acm_cert = aws.acm.Certificate(
                f"{self.basename}-vpn-srvracmcert",
                certificate_chain=ca_crt_pem,
                private_key=server_key_pem,
                certificate_body=server_cert_pem,
                opts=ResourceOptions(parent=self),
            )
        except FileNotFoundError as fnfe:
            raise ValueError(
                f"One or more configured TLS asset files could not be found "
                f"during VPN configuration: {fnfe}"
            )

    # TODO: ISSUE #100
    def create_vpn(self):
        """Creates/configures a Client VPN Endpoint for the private swimlane.

        In the case that the required configuration for the VPN ACM certificate
        does not exist or has issues, a message will be printed to the pulumi
        console and VPN configuration will cease.

        """

        try:
            self.create_vpn_acm_certificate()
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
            server_certificate_arn=self.vpn_server_acm_cert.arn,
            authentication_options=[
                {
                    "type": "certificate-authentication",
                    "root_certificate_chain_arn": self.vpn_server_acm_cert.arn,
                }
            ],
            client_cidr_block=self.config.get("vpn", "cidr-block"),
            connection_log_options={
                "enabled": True,
                "cloudwatch_log_group": self.vpn_log_group.name,
                "cloudwatch_log_stream": self.vpn_log_stream.name,
            },
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
