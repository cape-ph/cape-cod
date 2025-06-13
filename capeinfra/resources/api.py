"""Module of API resource abstractions.

Currently this is geared toward REST apis on AWS API Gateway. HTTP apis are not
yet supported.
"""

import json
from collections import defaultdict
from collections.abc import Mapping

import pulumi_aws as aws
from pulumi import AssetArchive, FileAsset, Output, ResourceOptions

import capeinfra
from capeinfra.iam import (
    get_api_lambda_authorizer_policy,
    get_api_policy,
    get_inline_role,
    get_vpce_api_invoke_policy,
)
from capeinfra.resources.compute import CapePythonLambdaLayer
from capeinfra.util.jinja2 import get_j2_template_from_path
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
            authorizer_path: Optional path to the source file for a lambda
                             authorizer for the API. If not provided, no
                             authorizer will be configured for the API.
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
        self.domain_name = domain_name

        # this will map the ids (string ids) from the config to a tuple of
        # (function name, Lambda Function Resource) so we can fill in the
        # open api file with lambda arns and also apply invoke permissions to
        # the lambdas once we have a rest api created (which requires the spec
        # template be rendered and the rest api resource created)
        self._ids_to_lambdas = {}

        self._configure_logging()
        self._create_api_ep_lambdas(resource_grants)
        self._create_api_authorizer_lambdas()
        self._render_spec()
        self._create_rest_api()
        self._deploy_stage(self.domain_name)

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

    def _create_api_ep_lambdas(
        self,
        res_grants: dict[str, list[Output]],
    ):
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

        # all of our lambda functs will get the capepy layer. and maybe more...
        funct_layers = [capeinfra.meta.capepy.lambda_layer.arn]
        funct_layer_args = self.config.get("layer_args", default=None)

        if funct_layer_args:

            api_lambda_layer = CapePythonLambdaLayer(
                f"{self.name}",
                **funct_layer_args,
            )
            funct_layers.append(api_lambda_layer.lambda_layer.arn)

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
                layers=funct_layers,
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
        template = get_j2_template_from_path(self.spec_path)

        # build up the keyword dict of tags/vals we'll pass off to the template
        # rendering. as that is done via `Output.all`, we can have unresolved
        # Outputs in the dict (e.g. arn's)
        spec_kwargs = {
            "api_name": self.api_name,
            "domain": self.domain_name,
            "authorizers": {},
            "handlers": {},
        }
        spec_kwargs["handlers"].update(
            {k: lf.arn for k, (_, lf) in self._ids_to_lambdas.items()}
        )

        for authz_name, authz_def in self._authorizers.items():

            spec_kwargs["authorizers"][authz_name] = {
                "type": authz_def["type"],
                "identity_sources": ",".join(
                    authz_def["identity_sources"] or []
                ),
                "result_cached_sec": authz_def["result_cached_sec"],
                "role": authz_def["role"].arn,
                "uri": authz_def["handler"].invoke_arn,
            }

        # as the lambda function arns are Output variables, we need to use the
        # standard wrapping of those in an apply in order to render the
        # template
        self._spec = Output.all(kw=spec_kwargs).apply(
            lambda args: template.render(**args["kw"])
        )

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

    def _create_api_authorizer_lambdas(
        self, res_grants: dict[str, list[Output]] | None = None
    ):
        """Create the Lambda function acting as the authorizer for an API.

        Args:
            res_grants: A mapping of resource types to a list of resource names
                        that the authorizer will be allowed to access. See
                        iam.py `get_api_authorizer_policy` for the specific
                        permissions granted. At this point our authorizers do
                        not need special access to anything (they absolutely
                        will in the future tho) so leave this value as None.
        """
        # TODO: res_grants will not work as originally intended here. we're
        #       potentially making more than one authorizer here and will need
        #       grants for each...
        self._authorizers = defaultdict(dict)

        # we setup a single log group for all authorizers, but each will get its
        # own stream
        self._authorizer_log_group = aws.cloudwatch.LogGroup(
            f"{self.name}-api-authz-logs",
            name=f"{self.name}-api-authz-logs",
            tags={
                "desc_name": (
                    f"{self.desc_name} {self.api_name} API authorizer Log Group"
                )
            },
            opts=ResourceOptions(parent=self),
        )

        for authorizer_name, authorizer_def in self.config.get(
            "authorizers", default={}
        ).items():
            authz_name = (
                f"{self.api_name}-api-default-authorizer"
                if authorizer_name == "default"
                else f"{authorizer_name}-authorizer"
            )

            self._authorizers[authz_name].update(authorizer_def)

            # Role for this lambda authorizer. At present all functions get
            # the same role functionally as we do not have specific resource
            # grants, but they will be different roles in actuality.
            # TODO: res_grants is not wired up in the policy doc function yet,
            #       so don't waste time figuring out why it doesn't work, need
            #       a way to specify grants for each authorizer
            # TODO: get_api_authorizer_policy probably needs work (if it still
            #       exists) when this gets wired up
            # policy_doc = (
            #     Output.all(grants=res_grants).apply(
            #         lambda kwargs: get_api_authorizer_policy(**kwargs)
            #     )
            #     if res_grants
            #     else None
            # )

            # create a role for the authorizer (lambda function)
            authorizer_lambda_role = get_inline_role(
                f"{self.name}-{authorizer_name}-lmbd-role",
                (
                    f"{self.desc_name} {self.config.get('desc')} "
                    f"{authorizer_name} lambda role"
                ),
                "lmbd",
                "lambda.amazonaws.com",
                # TODO: we will need a way to grant perms for this function if it
                #       needs to access resources oither than the lambda itself.
                #       that will be done in  a policy here using the res_grants
                #       passed in
                None,
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            )

            # Create our Lambda function for the authorizer
            # TODO: In the case that 2 apis use the same authorizer function
            #       code, this will create a new function with the same code if
            #       another already exists. need a way to reuse in that case
            authorizer_handler = aws.lambda_.Function(
                f"{self.name}-{authorizer_name}-lmbd-hndlr",
                role=authorizer_lambda_role.arn,
                code=AssetArchive(
                    {"index.py": FileAsset(authorizer_def["file"])}
                ),
                # TODO: this runtime should maybe be configurable long term
                runtime="python3.10",
                # logging_config=authorizer_logging_config,
                logging_config=(
                    {
                        "log_format": "Text",
                        "log_group": self._authorizer_log_group.name.apply(
                            lambda a: f"{a}"
                        ),
                    }
                    if authorizer_def.get("logging_enabled", False)
                    else None
                ),
                # in this case, the zip file for the lambda deployment is
                # being created by this code. and the zip file will be
                # called index. so the handler must be start with `index`
                # and the actual function in the script must be named
                # the same as the value here
                handler="index.lambda_handler",
                # TODO: will probs need variables when we get the authorizer fleshed
                #       out
                environment={"variables": {}},
                opts=ResourceOptions(parent=self),
                tags={
                    "desc_name": (
                        f"{self.desc_name} {self.api_name} API "
                        f"{authorizer_name} lambda authorizer function"
                    )
                },
            )

            self._authorizers[authz_name]["handler"] = authorizer_handler

            # create a role for the authorizer (api gateway to assume role and
            # call the lambda)
            # NOTE: As the authorizer is not hitting any additional AWS resources at
            #       present, this role is not really needed. In the near term this
            #       will change (e.g. the authorizer may need to hit an identity
            #       pool or something) in which case this role (and a policy doc
            #       that grants the access needed) will be required
            self._authorizers[authz_name]["role"] = get_inline_role(
                f"{self.name}-{authorizer_name}-authz-role",
                (
                    f"{self.desc_name} {self.config.get('desc')} "
                    f"API gateway {authorizer_name} authorizer role"
                ),
                "lmbd",
                "apigateway.amazonaws.com",
                # magic for all the lambda functions the authorizer can call
                (
                    Output.all(funct_arns=[authorizer_handler.arn]).apply(
                        lambda kwargs: get_api_lambda_authorizer_policy(
                            **kwargs
                        )
                    )
                ),
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
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
