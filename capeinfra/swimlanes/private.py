"""Resources for CAPE infra specific to the private swimlane.

This includes the private VPC, API/VPC endpoints and other top-level resources.
"""

import pulumi_aws as aws
from pulumi import AssetArchive, FileAsset, ResourceOptions

from ..iam import get_inline_role
from ..swimlane import ScopedSwimlane
from ..util.naming import disemvowel


class PrivateSwimlane(ScopedSwimlane):
    """Contains resources for the private swimlane of the CAPE Infra."""

    def __init__(self, name, *args, **kwargs):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)

        self.create_dap_api()

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

        # TODO: as this will be an api, there will be a number of functions
        #       most likely. we may want to consider making an api class that
        #       does some setup in a general manner and holds onto a mapping
        #       or list of functions eventually. this will almost certainly
        #       not be our only api and a reusable pattern would be nice.

        # TODO: we can probably have one lambda role for the whole API (or even
        #       multiple apis), we don't want to make one for each endpoint
        #       probably...
        self.api_lambda_role = get_inline_role(
            f"{self.basename}-dapapi-lmbd-role",
            f"{self.desc_name} data analysis pipeline lambda role",
            "lmbd",
            "lambda.amazonaws.com",
            # TODO: for right this second, the lambda functions needs no extra
            #       permissions via a role policy (the toy function currently
            #       only logs that it was called). This will almost certainly
            #       change, at which point a new function should be made in
            #       iam.py to build the policy doc. It is likely that this
            #       lambda would write to a queue, dynamodb, or otherwise put
            #       the params of the DAP into a holding place for the head
            #       node scheduler to get it going eventually. Until then, the
            #       role_policy param will be None
            None,
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
            opts=ResourceOptions(parent=self),
        )

        # TODO: in issue 61, this is where we ingest the openapi spec (`body`
        #       arg and needs to be json/yml string)
        self.dap_rest_api = aws.apigateway.RestApi(
            f"{self.basename}-dapapi",
            description="CAPE Data Analysis Pipeline API",
            # TODO: ISSUE 61 - we really probably want this all to be done via
            #       openapi spec. to do the integrations with lamba, we need to
            #       know the actual function name (with random hash) or find
            #       some other way. we'll construct a route/integration
            #       manually below in the meantime
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
                # TODO: this allows lambda on all endpoints and all methods for
                #       the api. may not be a great idea. or we may want
                #       different permissions for different parts of the API.
                #       not sure till we have a really fleshed out API.
                lambda arn: f"{arn}/*/*"
            ),
            opts=ResourceOptions(parent=self),
        )

        # TODO: ISSUE 61 - manual route/integration creation should be removed.
        #       probably not a great long term solution. see above comment on
        #       `RestApi.body` parameter and desire for openapi spec
        # NOTE: START manual route/integration
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

        # NOTE: END manual route/integration

        # Deployments and stages are needed to make APIs accessible. Another
        # reason we may wanna go with an API class to manage all of this in one
        # place
        self.dap_api_deployment = aws.apigateway.Deployment(
            f"{self.basename}-dapapi-dplymnt",
            rest_api=self.dap_rest_api.id,
            # TODO: we need to set this up to redeploy on api change. the
            #       deployment has a `triggers` param used to do this. there is
            #       an example here:
            #       https://www.pulumi.com/ai/answers/cc2eJai4VYGqawtkx44VXD/creating-aws-api-gateway-rest-api-with-python
            #       that uses an asset archive, which would be great with  our
            #       openapi spec file, but it doesn't work as-is (language server
            #       claims the dict[str, AssetArchive] is not compatible with
            #       triggers). Didn't want to waste time figuring it out before
            #       we have a full blown API, so this is left as an exercise
            #       for the reader later.
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
        # TODO: we need to pull the stage name from somewhere (e.g. the
        #       pulumi config) as the stage name is really tied to the type
        #       of deployment we're doing (dev, staging, prod, etc). there
        #       will probably be other things that will need the same thing.
        #       If we need to, we can also make an explicit
        #       aws.apigateway.Stage object if we need to (setting
        #       stage_name does this behind the scenes)
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
            # TODO: other things we should consider setting on the stage:
            #   - access_log_settings (per stage access logs)
            #   - client_certificate_id (per stage client certs)
            #   - documentation_version (doc version for the stage)
            #   - canary_settings (only if we end up doing canary deployments)
            opts=ResourceOptions(parent=self),
        )
