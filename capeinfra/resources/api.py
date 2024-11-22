"""Module of API resource abstractions.

Currently this is geared toward REST apis on AWS API Gateway. HTTP apis are not
yet supported.
"""

import json
import pathlib
from collections.abc import Mapping

import pulumi_aws as aws
from jinja2 import Environment, FileSystemLoader
from pulumi import AssetArchive, FileAsset, Output, ResourceOptions

import capeinfra
from capeinfra.iam import (
    get_api_policy,
    get_inline_role,
    get_vpce_api_invoke_policy,
)
from capepulumi import CapeComponentResource


class CapeRestApi(CapeComponentResource):
    """CapeComponentResource wrapping a REST API"""

    def __init__(
        self,
        name: str,
        api_name: str,
        spec_path: str,
        stage_suffix: str,
        env_vars: Mapping[str, Output[str] | str],
        resource_grants: dict[str, list[Output]],
        vpc_endpoint: aws.ec2.VpcEndpoint,
        domain_name: Output,
        *args,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The resource name for the REST API.
            api_name: A short name for the API the is used together with the
                      stage suffix and subdomain to construct the URI for the
                      API.
            spec_path: The path to the OpenAPI v3.0.1 spec for the API. NOTE:
                       the file must contain jinja2 template tags that will be
                       filled in for the lambda invoke path and otherwise must
                       conform to the format required by the AWS OpenAPI
                       parser.
            stage_suffix: The suffix for the stage to be deployed (e.g. "dev" or
                          "prod")
            env_vars: A mapping of environment variable labels to values that
                      will be passed into all Lambda handlers for the API.
            resource_grants: A mapping of resource types to a list of resource
                             names that will be allowed specific access for the
                             API. See iam.py `get_api_policy` for the specific
                             permissions granted. At this point only "tables"
                             and "queues" are allowed as keys.
            vpc_endpoint: The AWS VPC endpoint through which API gateway
                          requests will pass.
            domain_name: The domain name (e.g. api.cape-dev.org) on which this
                         API will reside.
        """
        super().__init__(
            "capeinfra:resources:CapeRestApi", name, *args, **kwargs
        )

        self.name = name
        self.api_name = api_name
        self.stage_suffix = stage_suffix
        self.env_vars = env_vars
        self.spec_path = spec_path
        self.api_vpcendpoint = vpc_endpoint

        # this will map the ids (string ids) from the config to a tuple of
        # (function name, Lambda Function Resource) so we can fill in the
        # open api file with lambda arns and also apply invoke permissions to
        # the lambdas once we have a rest api created (which requires the spec
        # template be rendered and the rest api resource created)
        self._ids_to_lambdas = {}

        self._configure_logging()
        self._create_api_lambdas(resource_grants)
        self._render_spec()
        self._create_rest_api()
        self._deploy_stage(domain_name)

    def _configure_logging(self):
        """Configure logging for the API.

        As we are currently making AWS APIGW REST APIs, this configures
        CloudWatch logging.

        NOTE: Configuring logging *does not* turn on logging for the API. This
              only configures permissions needed for logging and sets the
              format and log group. Turning on logging for an API seems to only
              be doable in the AWS console. Go to the stage in API gateway,
              find "Logging and Tracing", select "Edit" and then flip the
              CloudWatch logs toggle to "Errors Only" or "Errors and info logs"
              as needed. The "Access Log Destination ARN" should be set by this
              method, as should the format.
        """
        # Create an IAM role that API Gateway can assume to write logs
        self._log_group = aws.cloudwatch.LogGroup(
            # TODO: ISSUE #175
            f"{self.name}-loggrp",
        )

        self._log_role = get_inline_role(
            f"{self.name}-logrl",
            f"{self.desc_name} API Logging Role",
            "apigw",
            "apigateway.amazonaws.com",
            None,
            (
                "arn:aws:iam::aws:policy/service-role/"
                "AmazonAPIGatewayPushToCloudWatchLogs"
            ),
            opts=ResourceOptions(parent=self),
        )

        # decent general log format, we can tweak later if needed.
        self._log_fmt = {
            "requestId": "$context.requestId",
            "ip": "$context.identity.sourceIp",
            "caller": "$context.identity.caller",
            "user": "$context.identity.user",
            "requestTime": "$context.requestTime",
            "httpMethod": "$context.httpMethod",
            "resourcePath": "$context.resourcePath",
            "status": "$context.status",
            "protocol": "$context.protocol",
            "responseLength": "$context.responseLength",
        }

    def _create_api_lambdas(self, res_grants: dict[str, list[Output]]):
        """Create the Lambda functions acting as endpoint handlers for the API.

        Args:
            res_grants: A mapping of resource types to a list of resource names
                        that will be allowed specific access for the API. See
                        iam.py `get_api_policy` for the specific permissions
                        granted. At this point only "tables" and "queues" are
                        allowed as keys.
        """
        # Role for the lambda handlers of the API. At present all functions get
        # the same role.
        # NOTE: At this time we create one role for all possible operations of
        #       the API (e.g. if it needs to write to SQS in one function and
        #       read from DynamoDB in another, this role's policy must have both
        #       those grants). This may not be the long term implementation.
        self._api_lambda_role = get_inline_role(
            f"{self.name}-lmbd-role",
            f"{self.desc_name} {self.config.get('desc')} lambda role",
            "lmbd",
            "lambda.amazonaws.com",
            Output.all(
                grants=res_grants,
            ).apply(lambda kwargs: get_api_policy(**kwargs)),
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )

        # make functions from the configuration and save the mapping of the
        # function arn to the label we'll need to replace in the spec file.
        for hcfg in self.config.get("handlers", default=[]):
            # iterate the configured handlers and make the lambda functions for
            # each. we'll need to keep a mapping of the function id from the
            # config to the arn of the created function resource so we can
            # modify the openapi spec.

            # needed for a few args below. if not given or if there are missing
            # keys, we'll get default values
            funct_args = hcfg.get("funct_args", {})

            handler_lambda = aws.lambda_.Function(
                f"{self.name}-{hcfg['name']}-lmbdfn",
                role=self._api_lambda_role.arn,
                layers=[capeinfra.meta.capepy.lambda_layer.arn],
                code=AssetArchive({"index.py": FileAsset(hcfg["code"])}),
                environment={"variables": self.env_vars},
                opts=ResourceOptions(parent=self),
                # below are allowed to be configured externally and if not given
                # will be defaulted to values in pulumi docs (except description
                # which is given a sensible default)
                handler=funct_args.get("handler", "index.index_handler"),
                runtime=funct_args.get("runtime", "python3.10"),
                architectures=funct_args.get("architectures", ["x86_64"]),
                description=funct_args.get(
                    "description", f"{hcfg.get('name')} Lambda Function"
                ),
                memory_size=funct_args.get("memory_size", 128),
                timeout=funct_args.get("timeout", 3),
            )

            # update our mapping of function ids from the config to the name and
            # lambda function created
            self._ids_to_lambdas[hcfg["id"]] = (hcfg["name"], handler_lambda)

    def _render_spec(self):
        """Render the configured open api spec as a jijna2 template."""
        pth = pathlib.Path(self.spec_path)

        env = Environment(loader=FileSystemLoader(pth.parent))
        template = env.get_template(pth.name)

        # as the lamnda function arns are Output variables, we need to use the
        # standard wrapping of those in an apply in order to render the
        # template
        self._spec = Output.all(
            # the keyword args will contain {template_id: lambda_arn}
            kw={k: lf.arn for k, (_, lf) in self._ids_to_lambdas.items()}
        ).apply(lambda args: template.render(**args["kw"]))

    def _create_rest_api(self):
        """Create the RestApi wrapped by this class.

        This method also gives the REST API permission to invoke the Lambda
        functions handling the API endpoints.
        """
        # TODO: potentially use disable_execute_api_endpoint (force api to go
        #       through our custom domain in all cases). Leaving on for now as
        #       it's useful for testing.
        self.restapi = aws.apigateway.RestApi(
            f"{self.name}-restapi",
            description=f"{self.desc_name} REST API",
            endpoint_configuration=(
                aws.apigateway.RestApiEndpointConfigurationArgs(
                    types="PRIVATE",
                    vpc_endpoint_ids=(
                        self.api_vpcendpoint.id.apply(lambda i: [f"{i}"])
                    ),
                )
            ),
            policy=get_vpce_api_invoke_policy(vpce_id=self.api_vpcendpoint.id),
            body=self._spec.apply(lambda s: f"{s}"),
            opts=ResourceOptions(
                parent=self,
                # the api is dependent on all the lambda functions we kicked
                # off creation of earlier...
                depends_on=[lf for _, lf in self._ids_to_lambdas.values()],
            ),
        )

        # now that we have our rest api resource, we need to give it permission
        # to invoke the lambdas for each endpoint.
        for name, lf in self._ids_to_lambdas.values():
            aws.lambda_.Permission(
                f"{self.name}-{name}-allowlmbd",
                action="lambda:InvokeFunction",
                function=lf.arn,
                principal="apigateway.amazonaws.com",
                source_arn=self.restapi.execution_arn.apply(
                    # NOTE: this allows lambda on all endpoints and all methods
                    #       for the api. may not be a great idea. or we may
                    #       want different permissions for different parts of
                    #       the API. not sure till we have a really fleshed out
                    #       API.
                    lambda arn: f"{arn}/*/*"
                ),
                opts=ResourceOptions(parent=self),
            )

    def _deploy_stage(self, domain_name: Output):
        """Create a deployment and a stage for the API.

        Args:
            domain_name: The domain name (e.g. api.cape-dev.org) on which this
                         API will reside.
        """
        api_deployment = aws.apigateway.Deployment(
            f"{self.name}-restapi-dplymnt",
            rest_api=self.restapi.id,
            # TODO: ISSUE #65
            opts=ResourceOptions(
                parent=self,
            ),
        )

        # this ends up being the path after the fqdn for the subdomain to reach
        # this api
        self.stage_name = f"{self.api_name}-{self.stage_suffix}"

        # make a stage for the deployment manually.
        # NOTE: we could make this implicitly by just setting stage_name on the
        #       deployment resource, but there are warnings in the pulumi docs
        #       about weedy things that lead to deletion and addition of stages
        #       on redeployments if done this way, which ultimately leads to a
        #       service interruption.
        api_deployment_stage = aws.apigateway.Stage(
            f"{self.name}-dplymntstg",
            stage_name=self.stage_name,
            description=(
                f"CAPE {self.desc_name} {self.stage_name} deployment stage"
            ),
            deployment=api_deployment.id,
            rest_api=self.restapi.id,
            access_log_settings=aws.apigateway.StageAccessLogSettingsArgs(
                destination_arn=self._log_group.arn,
                format=json.dumps(self._log_fmt),
            ),
            variables={"cloudWatchRoleArn": self._log_role.arn},
            # TODO: ISSUE #67
            opts=ResourceOptions(parent=self),
        )

        aws.apigateway.BasePathMapping(
            f"{self.name}-bpm",
            domain_name=domain_name,
            rest_api=self.restapi.id,
            # base_path is part of the ultimate URL that will be used in,
            # hitting the API. stage_name is the stage name of the API the
            # request is sent to (and is not part of the URL)
            # NOTE: we require both to be the same
            base_path=api_deployment_stage.stage_name,
            stage_name=api_deployment_stage.stage_name,
        )