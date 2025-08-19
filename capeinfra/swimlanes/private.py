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
from capeinfra.datalake.datalake import DatalakeHouse
from capeinfra.iam import (
    get_bucket_reader_policy,
    get_bucket_web_host_policy,
    get_inline_role,
    get_instance_profile,
    get_nextflow_executor_policy,
    get_sqs_lambda_dap_submit_policy,
    get_vpce_api_invoke_policy,
)
from capeinfra.pipeline.dapregistry import DAPRegistry

# TODO: ISSUE #145 This import is to support the temporary dap results s3
#       handling.
from capeinfra.resources.api import CapeRestApi
from capeinfra.resources.certs import BYOCert
from capeinfra.resources.objectstorage import VersionedBucket
from capeinfra.swimlane import ScopedSwimlane, SubnetType
from capeinfra.util.file import file_as_string
from capeinfra.util.jinja2 import (
    get_j2_template_from_path,
    get_j2_template_from_str,
)
from capeinfra.util.naming import disemvowel
from capepulumi import CapeConfig


class PrivateSwimlane(ScopedSwimlane):
    """Contains resources for the private swimlane of the CAPE Infra."""

    # ids for the ALBs we will set up in this class
    APPLICATION_ALB = "application"
    API_ALB = "api"

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
            "subnets": [{"name": "public", "cidr-block": "10.0.1.0/24"}],
            "static-apps": [],
            "api": {
                "subdomain": "api",
                "stage": {
                    "meta": {
                        "stage-suffix": "dev",
                    },
                },
                "apis": [],
            },
            "compute": {},
            "vpn": {
                "cidr-block": "10.1.0.0/22",
                "transport-proto": "udp",
            },
        }

    def __init__(self, name, data_lake_house: DatalakeHouse, *args, **kwargs):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)
        # TODO: ISSUE #153 is there a better way to expose the auto assets
        #       bucket since we're now passing it to every client that needs a
        #       lambda script? Same for data catalog (which is passed to the
        #       swimlane base class)

        aws_config = Config("aws")
        self.aws_region = aws_config.require("region")
        self.data_lake_house = data_lake_house

        # will contain a mapping of env var labels to resource names and types.
        # these may be used in api configuration to state the need for a
        # particular env var to be passed into the api lambda handlers. by
        # virtue of configuring support for these vars, required resource
        # permissions will also be added for the lambda.
        # TODO: this may not really be what we want long term. ideally we would
        #       be able to configure adding things like sqs queues and such
        #       without having to change code to expose a new env var. there are
        #       some gotchas (e.g. some things like the DAP registry are needed
        #       by APIs but do not belong to a specific api, so configuration
        #       would need to be done at a different level than if it was just
        #       for use by an api. additionally, there are notification lambdas,
        #       roles, and policies to consider). another option is to better
        #       formalize this exposed env var concept and make a class that
        #       does some form of registration on instantiation so that we are
        #       not hard coding the env var label in this class.
        self._exposed_env_vars = {}

        self._exposed_env_vars.setdefault(
            "DDB_REGION",
            {
                "resource_name": self.aws_region,
                "type": "metadata",
            },
        )

        self._exposed_env_vars.setdefault(
            "ETL_ATTRS_DDB_TABLE",
            {
                "resource_name": self.data_lake_house.etl_attr_ddb_table.name,
                "type": "table",
            },
        )

        self._exposed_env_vars.setdefault(
            "CRAWLER_ATTRS_DDB_TABLE",
            {
                "resource_name": self.data_lake_house.crawler_attrs_ddb_table.name,
                "type": "table",
            },
        )

        self.create_analysis_pipeline_registry()
        self.create_static_web_resources()
        self.create_application_instances()
        # static and instance apps share an alb
        self._create_app_alb()
        self.create_private_api_resources()
        # identity pool is created well before we get here, but we can't add
        # roles/policies/attachments before we know the app clients which
        # haven't been added till now.
        capeinfra.meta.principals.add_principals()
        self._create_hosted_domain()
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
            if self._exposed_env_vars[ev]["resource_name"] not in res:
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
        self.analysis_pipeline_registry = DAPRegistry(
            "cape-dap-registry",
            opts=ResourceOptions(parent=self),
            desc_name=(f"{self.desc_name} Analysis Pipeline Registry"),
        )

        # read access to this this resource can be configured via the deployment
        # config (for api lambdas), so add it to the bookkeeping structure for
        # that
        self._exposed_env_vars.setdefault(
            "DAP_REG_DDB_TABLE",
            {
                "resource_name": self.analysis_pipeline_registry.analysis_pipeline_registry_ddb_table.name,
                "type": "table",
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
        sa_short_name = sa_cfg.get("short_name", default=None)
        sa_fqdn = sa_cfg.get("fqdn", default=None)
        sa_dir = sa_cfg.get("dir", default=None)

        if None in (sa_name, sa_short_name, sa_fqdn, sa_dir):
            msg = (
                f"Static App {sa_name or 'UNNAMED'} contains one or more "
                "invalid configuration values that are required. The "
                "application will not be deployed. Check the app name, app "
                "short name, fqdn, and repo directory."
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

        self.static_apps[sa_name]["short_name"] = sa_short_name

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
    def _create_app_alb(self):
        """Create the application load balancer for applications.

        Static (S3) and instance based applications share the same load
        balancer.
        """
        self.create_alb(
            self.APPLICATION_ALB,
            [s for _, s in self.get_subnets_by_type(SubnetType.APP).items()],
            self.domain_cert.acmcert,
        )

        # attach the instance applications first as they have simpler listener
        # rules and need no path mucking
        for ia_name, ia_info in self.instance_apps.items():
            self.albs[self.APPLICATION_ALB].add_instance_app_target(
                ia_info["instance"],
                ia_name,
                ia_info["short_name"],
                ia_info["fqdn"],
                port=443,
                proto="HTTPS",
                fwd_port=ia_info["port"],
                fwd_proto=ia_info["proto"],
                hc_args=ia_info["hc_args"],
            )

        # then attach the static app targets to the alb. we want their listeners
        # to have lower priority as they may muck around with the path after the
        # hostname before forwarding to the target
        for sa_name, sa_info in self.static_apps.items():
            self.albs[self.APPLICATION_ALB].add_static_app_target(
                sa_info["bucket"].bucket,
                self.static_app_vpcendpoint,
                sa_name,
                sa_info["short_name"],
                port=443,
                proto="HTTPS",
            )

    # TODO: ISSUE #176
    def _create_api_alb(self):
        """Create the application load balancer for private apis."""

        self.create_alb(
            self.API_ALB,
            [s for _, s in self.get_subnets_by_type(SubnetType.APP).items()],
            self.domain_cert.acmcert,
        )

        # TODO: similar to the static apps, this should operate on a loop of
        #       config items

        # attach the api gateway targets to the alb
        for api_info in self.apis.values():
            self.albs[self.API_ALB].add_api_target(
                self.api_vpcendpoint,
                api_info["deploy"].stage_name,
                api_info["spec"]["short_name"],
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
            subnet_ids=[
                s.id
                for _, s in self.get_subnets_by_type(SubnetType.VPN).items()
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

        for spec in self.config.get("api", "apis"):
            self.apis.setdefault(spec["name"], {"spec": spec})

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
            subnet_ids=[
                s.id
                for _, s in self.get_subnets_by_type(SubnetType.VPN).items()
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

        # read access to this this resource can be configured via the deployment
        # config (for api lambdas), so add it to the bookkeeping structure for
        # that
        self._exposed_env_vars.setdefault(
            "USER_ATTRS_DDB_TABLE",
            {
                "resource_name": capeinfra.meta.principals.user_attrs_ddb_table.name,
                "type": "table",
            },
        )

        # TODO: we'll really want this to create all private apis in a generic
        #       method based on config eventually
        for api_name in self.apis.keys():
            self._deploy_api(api_name)

        self._create_api_alb()

    def create_application_instances(self):
        """Creates resources related to private swimlane web resources."""

        self.instance_apps = {}

        app_instance_pub_key = self.config.get(
            "instance-apps", "pub-key", default=None
        )

        app_instance_cfgs = self.config.get(
            "instance-apps", "instances", default=[]
        )

        # NOTE: for now all instances will be managed via the same keypair
        self.ec2inst_keypair = aws.ec2.KeyPair(
            f"{self.basename}-ec2i-kp",
            key_name=f"{self.basename}-ec2inst-key",
            public_key=file_as_string(app_instance_pub_key),
        )

        # Setup all instance app clients
        for aicfg in app_instance_cfgs:
            ia_name = aicfg["name"]

            # first process the user data if applicable
            domain = f"{aicfg['subdomain']}.{self.domain_name}"

            # if a client is asked to be configured, add it to the user pool
            cognito_client = aicfg.get("cognito_client", None)
            if cognito_client is not None:

                def url_template(url):
                    return get_j2_template_from_str(url).render(domain=domain)

                for url_field in ["logout_urls", "callback_urls"]:
                    if url_field in cognito_client:
                        cognito_client[url_field] = list(
                            map(url_template, cognito_client[url_field])
                        )
                capeinfra.meta.principals.add_client(ia_name, cognito_client)

        # TODO: Clean up this implementation. This exists here to guarantee the
        # identity pool is created after all instance application clients but
        # before any templates are rendered to make sure the identity pool id is
        # available. (Includes for loop above and causing 2x looping over the
        # instance applications)
        # Add identity pool after setting up clients
        capeinfra.meta.principals.add_identity_pool()

        for aicfg in app_instance_cfgs:
            ia_name = aicfg["name"]

            # TODO: ISSUE #186

            # create the instance profile up front. we'll need to pass the role
            # of the profile into instance user data templates
            instance_profile = self._create_instance_profile(
                ia_name, aicfg.get("services", [])
            )

            # first process the user data if applicable
            domain = f"{aicfg['subdomain']}.{self.domain_name}"

            # if a client is asked to be configured, add it to the user pool
            cognito_client = aicfg.get("cognito_client", None)

            user_data = None
            rebuild_on_ud_change = False
            ud_info = aicfg.get("user_data", None)

            if ud_info is not None:
                rebuild_on_ud_change = ud_info["rebuild_on_change"]
                template = get_j2_template_from_path(ud_info["template"])

                template_args: dict[str, Output | str] = {}
                template_args["domain"] = domain
                # if there is a cognito client, pass in the necessary client
                # information
                if ia_name in capeinfra.meta.principals.clients:
                    template_args["cognito_identity_pool_id"] = (
                        capeinfra.meta.principals.identity_pool.id
                    )
                    client = capeinfra.meta.principals.clients[ia_name]
                    template_args["cognito_client_id"] = client.id
                    template_args["cognito_client_secret"] = (
                        client.client_secret
                    )
                    template_args["cognito_domain"] = (
                        capeinfra.meta.principals.user_pool.domain.apply(
                            lambda d: f"https://{d}.auth.{self.aws_region}.amazoncognito.com"
                        )
                    )

                # TODO: we are passing in the aws region to all instance
                #       templates. Not really a big deal i don't think,
                #       but it does pollute the namespace a bit. perhaps
                #       consider a Context object based on instance type or
                #       something like that?
                template_args["aws_region"] = self.aws_region

                template_args["vars"] = ud_info.get("vars", {})

                def render(tmpl):
                    return lambda args: tmpl.render(**args["vars"], **args)

                user_data = Output.all(**template_args).apply(render(template))

            # now create the instance
            # TODO: ISSUE #184
            for snt in aicfg["subnet_types"]:
                subnets = self.get_subnets_by_type(snt)
                for snn, sn in subnets.items():
                    self.instance_apps[aicfg["name"]] = {
                        "instance": aws.ec2.Instance(
                            f"{self.basename}-{snn}-{aicfg['name']}-ec2i",
                            ami=aicfg["image"],
                            associate_public_ip_address=aicfg.get(
                                "public_ip", False
                            ),
                            instance_type=aicfg.get(
                                "instance_type", "t3a.medium"
                            ),
                            subnet_id=sn.id,
                            key_name=self.ec2inst_keypair.key_name,
                            # TODO: ISSUE #112
                            vpc_security_group_ids=[
                                self.vpc.default_security_group_id
                            ],
                            tags={
                                # NOTE: This is like the VPC in that to set the name to be
                                #       displayed in the AWS console you must do it via the
                                #       tag "Name"
                                "Name": f"{self.basename}-{aicfg['name']}-ec2i",
                                "desc_name": (
                                    f"{self.desc_name} {aicfg['name']} application EC2 "
                                    "instance"
                                ),
                            },
                            user_data=user_data,
                            user_data_replace_on_change=rebuild_on_ud_change,
                            iam_instance_profile=(
                                instance_profile.name
                                if instance_profile is not None
                                else None
                            ),
                            opts=ResourceOptions(parent=self),
                        ),
                        "short_name": aicfg["short_name"],
                        "fqdn": domain,
                        "port": aicfg.get("port", None),
                        "proto": aicfg.get("protocol", None),
                        "hc_args": aicfg.get("healthcheck", None),
                    }

    def _create_instance_profile(self, ia_name: str, services: list[str] = []):
        """Return an instance profile with grants needed for provided services.

        Args:
            ia_name: The name of the instance app.
            services: An optional list of service names from the instance app
                      config that policy grants are needed for.
        Returns:
            The instance profile with the specified grants
        """

        statements = []
        policy_attachments = []

        if "athena" in services:
            # TODO: issue #185
            statements.append(
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:ListBucket",
                        "s3:PutObject",
                    ],
                    "Resource": [
                        "arn:aws:s3:::*/*",
                        "arn:aws:s3:::*",
                    ],
                }
            )
            policy_attachments.append(
                "arn:aws:iam::aws:policy/AmazonAthenaFullAccess"
            )

        if "cognito" in services:
            policy_attachments.append(
                "arn:aws:iam::aws:policy/AmazonCognitoPowerUser"
            )

        if "s3" in services:
            # TODO: issue #186 - would be great if we could specify the exact
            #                    resource we're allowing for reading. In this
            #                    case (at time of writing) it's the meta bucket
            #                    (probably with a specific prefix)
            statements.append(
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                    ],
                    "Resource": [
                        "arn:aws:s3:::*/*",
                        "arn:aws:s3:::*",
                    ],
                }
            )
            # NOTE: this may need to change. right now we just need EC2
            #       instances specified with `s3` service to be read only.
            policy_attachments.append(
                "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
            )

        # for shortening line and making linter happy
        desc_services = (
            ":".join(services) if services else "<NO SERVICES CONFIGURED>"
        )

        ec2_role = get_inline_role(
            f"{self.basename}-ec2role-{disemvowel(ia_name)}",
            f"{self.desc_name} EC2 instance role for {desc_services} access",
            "ec2",
            "ec2.amazonaws.com",
            (
                None  # no role policy if no statements
                if not statements
                else json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": statements,
                    }
                )
            ),
            policy_attachments,
            opts=ResourceOptions(parent=self),
        )

        return get_instance_profile(
            self.basename, ec2_role, name_suffix=disemvowel(ia_name)
        )

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
                sa_info["bucket"].bucket.bucket, sa_name, self.APPLICATION_ALB
            )

        # and a zone record for each instance application
        for ia_name, ia_info in self.instance_apps.items():

            self.create_private_domain_alb_record(
                ia_info["fqdn"], ia_name, self.APPLICATION_ALB
            )

        # all apis are at the same subdomain with different paths off of that
        # sub. we only need to create a single record in route53 for this (just
        # for the subdomain itself).

        self.create_private_domain_alb_record(
            self.api_fqdn,
            "api",
            self.API_ALB,
        )

        # and DNS for the zone
        # TODO: This feels like DNS should be associated with all our subnets
        #       (except maybe NAT). Though we associate only with VPN subnets
        #       here, all internal DNS succeeds regardless of subnet.
        self.create_private_hosted_dns(
            [s for _, s in self.get_subnets_by_type(SubnetType.VPN).items()],
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

        # For client VPN, all traffic egress to the internet will be allowed
        auth_rule_inet = aws.ec2clientvpn.AuthorizationRule(
            f"{self.basename}-vpninet-authzrl",
            client_vpn_endpoint_id=self.client_vpn_endpoint.id,
            # access internet
            target_network_cidr="0.0.0.0/0",
            # TODO: ISSUE #101
            authorize_all_groups=True,
            opts=ResourceOptions(parent=self.client_vpn_endpoint),
        )

        # associate the VPN endpoint with all VPN subnets and setup auth
        # rules/routes for the vpn subnets
        for sn_name, sn in self.get_subnets_by_type(SubnetType.VPN).items():

            # The client endpoint needs to be associated with one or more
            # subnets
            # TODO: ISSUE #100
            subnet_association = aws.ec2clientvpn.NetworkAssociation(
                f"{self.basename}-{sn_name}assctn",
                client_vpn_endpoint_id=self.client_vpn_endpoint.id,
                subnet_id=sn.id,
                opts=ResourceOptions(
                    depends_on=[self.client_vpn_endpoint],
                    parent=self.client_vpn_endpoint,
                ),
            )

            # By default, the client endpoint will get a route to the VPC itself. we
            # need to also authorize the endpoint to route traffic to the VPN
            # subnets and to the internet (through the VPN subnets). This requires
            # an auth rule and a route for the internet case and just an auth rule
            # for the VPN case

            # NOTE: leaving as 2 explicit auth rule creations instead of
            # trying to reduce DRY violation in a loop or something on purpose. Do
            # not know how this is going to shake out in the long term and we may
            # end up with more/fewer rules. :shrug: we can refactor when that
            # becomes clear

            aws.ec2clientvpn.AuthorizationRule(
                f"{self.basename}-{sn_name}-authzrl",
                client_vpn_endpoint_id=self.client_vpn_endpoint.id,
                # access vpn subnet only
                target_network_cidr=(sn.cidr_block.apply(lambda cb: f"{cb}")),
                # TODO: ISSUE #101
                authorize_all_groups=True,
                opts=ResourceOptions(parent=self.client_vpn_endpoint),
            )

            # Route to internet (egress only)
            aws.ec2clientvpn.Route(
                f"{self.basename}-{sn_name}inet-rt",
                client_vpn_endpoint_id=self.client_vpn_endpoint.id,
                destination_cidr_block="0.0.0.0/0",
                target_vpc_subnet_id=sn.id,
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
