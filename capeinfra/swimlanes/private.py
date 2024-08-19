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
            "compute": {},
        }

    def create_dap_api(self):
        """Create the data analysis pipeline API for the private swimlane."""

        # TODO: ISSUE #62

        self.api_lambda_role = get_inline_role(
            f"{self.basename}-dapapi-lmbd-role",
            f"{self.desc_name} data analysis pipeline lambda role",
            "lmbd",
            "lambda.amazonaws.com",
            # TODO: ISSUE #64
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
