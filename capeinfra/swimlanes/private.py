"""Resources for CAPE infra specific to the private swimlane.

This includes the private VPC, API/VPC endpoints and other top-level resources.
"""

import json

import pulumi_aws as aws
from pulumi import (
    AssetArchive,
    Config,
    FileAsset,
    Output,
    ResourceOptions,
    warn,
)
from pulumi_synced_folder import S3BucketFolder

import capeinfra
from capeinfra.iam import (
    get_bucket_reader_policy,
    get_bucket_web_host_policy,
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
from capeinfra.pipeline.data import DataCrawler, EtlJob
from capeinfra.resources.api import CapeRestApi
from capeinfra.resources.certs import BYOCert
from capeinfra.resources.objectstorage import VersionedBucket
from capeinfra.swimlane import ScopedSwimlane
from capeinfra.util.naming import disemvowel
from capepulumi import CapeConfig


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
            # NOTE: we do not include a default cert setup other than None here
            #       as we do not provide default certs in this repo. we want
            #       pulumi to fail if this is not provided.
            "tls": None,
            "public-subnet": {
                "cidr-block": "10.0.0.0/24",
            },
            "private-subnets": [],
            "static-apps": [],
            "api": {
                "subdomain": "api",
                "stage": {
                    "meta": {
                        "stage-suffix": "dev",
                    },
                },
                "apis": {},
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
        # TODO: ISSUE #153 is there a better way to expose the auto assets
        #       bucket since we're now passing it to every client that needs a
        #       lambda script? Same for data catalog (which is passed to the
        #       swimlane base class)

        aws_config = Config("aws")
        self.aws_region = aws_config.require("region")

        # will contain a mapping of env var labels to resource names and types.
        # these may be used in api configuration to state the need for a
        # particular env var to be passed into the api lambda handlers. by
        # virtue of configuring support for these vars, required resource
        # permissions will also be added for the lambda.
        self._exposed_env_vars = {}

        self.create_analysis_pipeline_registry()
        self.create_dap_submission_queue()
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

    # TODO: ISSUE #61
    def _deploy_api(self, api_name):
        """Deploy an API for the private swimlane.

        NOTE: At this time only one API is expected and supported. All others
              will be be logged as a warning during pulumi operations until this
              changes.

        Args:
            api_name: The name of the API as configured.
        """
        # create a new CapeRestApi object for the given api name

        # construct the env_vars and resource_grants values based on the
        # configuration.
        # NOTE: if there's a bad env var in here, we'll let the KeyError go to
        #       halt the deployment.
        env_vars = {}
        resource_grants = {}
        for ev in self.apis[api_name]["spec"].get("env_vars", []):
            env_vars.setdefault(ev, self._exposed_env_vars[ev]["resource_name"])
            res = resource_grants.setdefault(
                self._exposed_env_vars[ev]["type"], []
            )
            # we don't want to end up with the same thing in the list more than
            # once. could go with a set or filter, or we could just check if
            # it's in there before adding...
            if not self._exposed_env_vars[ev]["resource_name"] in res:
                res.append(self._exposed_env_vars[ev]["resource_name"])

        self.apis[api_name]["deploy"] = CapeRestApi(
            f"{self.basename}-{api_name}-api",
            api_name,
            self.apis[api_name]["spec"]["spec_file"],
            self.api_stage_suffix,
            env_vars,
            resource_grants,
            self.api_vpcendpoint,
            self.apigw_domainname.domain_name,
            config=self.apis[api_name]["spec"],
            desc_name=f"{self.apis[api_name]['spec']['desc']}",
            opts=ResourceOptions(parent=self),
        )

    def create_analysis_pipeline_registry(self):
        """Sets up an analysis pipeline registry database."""
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

        # read access to this this resource can be configured via the deployment
        # config (for api lambdas), so add it to the bookkeeping structure for
        # that
        self._exposed_env_vars.setdefault(
            "DAP_REG_DDB_TABLE",
            {
                "resource_name": self.analysis_pipeline_registry_ddb_table.name,
                "type": "table",
            },
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
            layers=[capeinfra.meta.capepy.lambda_layer.arn],
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/sqs_dap_submit_lambda.py"
                    )
                }
            ),
            runtime="python3.10",
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

        # read access to this this resource can be configured via the deployment
        # config (for api lambdas), so add it to the bookkeeping structure for
        # that
        self._exposed_env_vars.setdefault(
            "DAP_QUEUE_NAME",
            {
                "resource_name": self.dap_submit_queue.name,
                "type": "queue",
            },
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

        if None in (sa_name, sa_fqdn, sa_dir):
            msg = (
                f"Static App {sa_name or 'UNNAMED'} contains one or more "
                "invalid configuration values that are required. The "
                "application will not be deployed. Check the app name, fqdn, "
                "and repo directory."
            )

            warn(msg)
            raise ValueError(msg)

        # NOTE:
        # self.static_apps format:
        # {
        #   app_name: {
        #       "bucket": VersionedBucket,
        #       "cert": aws.acm.Certificate,
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

        # deploy the static app files by compying all directory contents to s3
        S3BucketFolder(
            f"{self.basename}-{sa_name}-syncfldr",
            path=sa_dir,
            bucket_name=self.static_apps[sa_name]["bucket"].bucket.bucket,
            acl=aws.s3.CannedAcl.BUCKET_OWNER_FULL_CONTROL,
            include_hidden_files=True,
            opts=ResourceOptions(parent=self),
        )

    # TODO: ISSUE #176
    def _create_static_app_alb(self):
        """Create the application load balancer for static applications."""

        self.create_alb(
            "static",
            [
                self.private_subnets["vpn"],
                self.private_subnets["vpn2"],
            ],
            self.domain_cert.acmcert,
        )

        # attach the static app targets to the alb
        for sa_name in self.static_apps.keys():
            self.albs["static"].add_static_app_target(
                self.static_app_vpcendpoint,
                sa_name,
                port=443,
                proto="HTTPS",
            )

    # TODO: ISSUE #176
    def _create_api_alb(self):
        """Create the application load balancer for private apis."""

        self.create_alb(
            "api",
            [
                self.private_subnets["vpn"],
                self.private_subnets["vpn2"],
            ],
            self.domain_cert.acmcert,
        )

        # TODO: similar to the static apps, this should operate on a loop of
        #       config items

        # attach the api gateway targets to the alb
        for api_info in self.apis.values():
            self.albs["api"].add_api_target(
                self.api_vpcendpoint,
                api_info["deploy"].stage_name,
                port=443,
                proto="HTTPS",
            )

    # TODO: ISSUE #176
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

    # TODO: ISSUE #176
    def create_private_api_resources(self):
        """Creates resources related to private swimlane apis."""

        # name of the api subdomain (not the full sub hostname)
        self.api_subdomain = self.config.get("api", "subdomain", default=None)
        # suffix for apis (e.g. `dev`, `prod`, etc)
        self.api_stage_suffix = self.config.get(
            "api", "stage", "meta", "stage-suffix"
        )

        # fail if we don't have an api subdomain or suffix configured
        if None in (self.api_subdomain, self.api_stage_suffix):
            raise ValueError(
                "One or both of the API subdomain/API stage suffix are not "
                "defined."
            )

        self.api_fqdn = f"{self.api_subdomain}.{self.domain_name}"

        # this will hold api specifications (config info) in "specs" key and
        # deployment info in "deploy" key
        self.apis = {}

        for name, spec in self.config.get("api", "apis").items():
            self.apis.setdefault(name, {"spec": spec})

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

        aws.ec2.VpcEndpointPolicy(
            f"{self.basename}-api-vpcepplcy",
            vpc_endpoint_id=self.api_vpcendpoint.id,
            # TODO: ISSUE #135
            policy=get_vpce_api_invoke_policy(vpc_id=self.vpc.id),
            opts=ResourceOptions(parent=self),
        )

        self.apigw_domainname = aws.apigateway.DomainName(
            f"{self.basename}-apigw-dn",
            domain_name=self.api_fqdn,
            regional_certificate_arn=(self.domain_cert.acmcert.arn),
            endpoint_configuration={
                "types": "REGIONAL",
            },
        )

        # TODO: we'll really want this to create all private apis in a generic
        #       method based on config eventually
        for api_name in self.apis.keys():
            self._deploy_api(api_name)

        self._create_api_alb()

    def _create_hosted_domain(self):
        """Create the private zone for the swimlane.

        This must be done after setting up the ALB.
        """

        # setup the private hosted zone. this is totally inside our private
        # vpc, so it doesn't need to be registered anywhere public unless used
        # for public facing resources as well.
        self.create_hosted_domain(self.domain_name)

        # we need a zone record per static app bucket
        for sa_name, sa_info in self.static_apps.items():

            self.create_private_domain_alb_record(
                sa_info["bucket"].bucket.bucket, sa_name, "static"
            )

        # all apis are at the same subdomain with different paths off of that
        # sub. we only need to create a single record in route53 for this (just
        # for the subdomain itself).

        self.create_private_domain_alb_record(
            self.api_fqdn,
            "api",
            "api",
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
                desc_name="CAPE Private Swimlane VPN ACM BYOCert",
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

        aws.ec2clientvpn.AuthorizationRule(
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
            capeinfra.meta.automation_assets_bucket.bucket,
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
            layers=[capeinfra.meta.capepy.lambda_layer.arn],
            code=AssetArchive(
                {
                    # TODO: ISSUE #150 this script is usable as is for any glue
                    #       job sqs handler, with the caveat that the glue job
                    #       has to support a RAW_BUCKET_NAME and OBJECT_KEY
                    #       env var (and the same sqs message format). it might
                    #       be worth changing the job spec to take a
                    #       `SRC_BUCKET_NAME` instead of `RAW` since not all
                    #       sources will be really raw data.
                    "index.py": FileAsset(
                        "./assets/lambda/sqs_etl_job_trigger_lambda.py"
                    )
                }
            ),
            runtime="python3.10",
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
            layers=[capeinfra.meta.capepy.lambda_layer.arn],
            code=AssetArchive(
                {
                    "index.py": FileAsset(
                        "./assets/lambda/new_dap_results_queue_notifier_lambda.py"
                    )
                }
            ),
            runtime="python3.10",
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
