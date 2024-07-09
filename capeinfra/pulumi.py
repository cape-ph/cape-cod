"""Module of subclasses of pulumi objects."""

import copy
import typing

import pulumi_aws as aws
from pulumi import (
    AssetArchive,
    ComponentResource,
    FileAsset,
    Input,
    ResourceOptions,
)

from .iam import get_tailored_role


class DescribedComponentResource(ComponentResource):
    """Extension of ComponentResource that takes a descriptive name."""

    def __init__(self, comp_type, name, *args, desc_name=None, **kwargs):
        """Constructor.

        Takes all the same args/kwargs as pulumi's ComponentResource in addition
        to the ones below.

        Args:
            desc_name: A descriptive name that can be added to tags for child
                       components because names are so restricted in length.
        """
        super().__init__(comp_type, name, *args, **kwargs)
        self.name = name
        self.desc_name = desc_name


class ObjectStorageTriggerable(DescribedComponentResource):
    """Base class for a object storage triggerable (e.g. AWS Lambda) resource.

    This is a base class and should not be instatiated directly.
    """

    def __init__(self, *args, **kwargs):
        """Constructor."""
        super().__init__(*args, **kwargs)
        # NOTE: ideally this would work for any cloud provider, but for now
        #       everything is AWS only, hence the hardcodes here
        self.trigger_role = None
        self.service_prefix = "lmbda"
        self.service = "lambda.amazonaws.com"
        self.service_policy_attachment = (
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )

    @property
    def source_buckets(self) -> list[aws.s3.BucketV2]:
        """Property representing the source buckets that cause the trigger.

        Some subclasses will have a list of source buckets and others will have
        a single source bucket. This property gives a simple way to always have
        a list regardless of internals.

        THIS PROPERTY IS REQUIRED FOR ALL SUBCLASSES.

        Returns:
            A list of source buckets that cause the trigger.
        """
        raise NotImplementedError(
            "ObjectStorageTriggerable subclasses must implement "
            "source_buckets property"
        )

    def add_trigger_function(
        self,
        script_path: str,
        role_policy: Input,
        env_vars: dict[str, typing.Any] | None,
        opts: ResourceOptions | None,
    ):
        """Adds a trigger function for this resource.

        Args:
            script_path: The path to the script that is run on the trigger. This
                         path is from the perspective of the deployment
                         repository and not the deployed system.
            role_policy: The role policy for the role this trigger runs as. E.g.
                         if this is a glue crawler, the role policy would
                         specify start/get crawler actions for a specific
                         crawler resource.
            env_vars: A dict of environment variables to pass onto the triggered
                      script.
            opts: The resource options to set for the triggered function.
        """
        # get a role for the trigger function
        self.trigger_role = get_tailored_role(
            self.name,
            f"{self.desc_name} trigger role",
            self.service_prefix,
            self.service,
            role_policy,
            self.service_policy_attachment,
            opts,
        )

        # Create our Lambda function that triggers the given glue job
        self.trigger_function = aws.lambda_.Function(
            f"{self.name}-{self.service_prefix}fnct",
            role=self.trigger_role.arn,
            # NOTE: Lambdas want a zip file as opposed to an s3 script location
            code=AssetArchive({"index.py": FileAsset(script_path)}),
            runtime="python3.11",
            # in this case, the zip file for the lambda deployment is
            # being created by this code. and the zip file will be
            # called index. so the handler must be start with `index`
            # and the actual function in the script must be named
            # the same as the value here
            handler="index.index_handler",
            environment={
                "variables": env_vars,
            },
            opts=opts,
            tags={"desc_name": f"{self.desc_name} trigger function"},
        )

    def create_object_notifications(
        self,
        prefix: str | None = None,
        suffixes: list | None = None,
        opts: ResourceOptions | None = None,
    ):
        """Creates object storage notifications that trigger our function.

        NOTE: In the case of AWS, there will be one set of function args
              created for each suffix given (or a default set of args if no
              suffixes are given) due to how AWS handles suffix filtering.

        Args:
            prefix: An optional prefix on the object storage key (e.g. `subdir`
                    as the prefix would trigger on `subdir/*` in object
                    storage).
            suffixes: An optional list of suffixes to filter on before
                      triggering (e.g. ["docx", "xlsx"] would limit triggering
                      to only happen on files of those types)
            opts: An optional ResourceOptions object to pass on to all created
                  ComponentResources created here (e.g. permissions, bucket
                  notifications)
        """
        perms = []
        funct_args = []
        opts = opts or ResourceOptions(parent=self)

        suffixes = suffixes or [""]
        prefix = prefix or ""

        # Give our function permission to invoke a function for each source
        # bucket we're configured for
        for bucket in self.source_buckets:
            perms.append(
                aws.lambda_.Permission(
                    f"{self.name}-allow-{self.service_prefix}",
                    action="lambda:InvokeFunction",
                    function=self.trigger_function.arn,
                    principal="s3.amazonaws.com",
                    source_arn=bucket.arn,
                    opts=opts,
                )
            )

            # create a set of function args for each suffix given (or a default
            # set of args if there were no suffixes given).
            for s in suffixes:
                funct_args.append(
                    aws.s3.BucketNotificationLambdaFunctionArgs(
                        events=["s3:ObjectCreated:*"],
                        lambda_function_arn=self.trigger_function.arn,
                        filter_prefix=prefix,
                        filter_suffix=s,
                    )
                )

            # we're setting a dependency on the options object that will be
            # different per loop iteration, so just make a local copy we can
            # change as needed
            localopts = copy.copy(opts)
            localopts.depends_on = perms

            # Add a bucket notification to trigger our functions automatically
            # if they were configured.
            aws.s3.BucketNotification(
                f"{self.name}-s3ntfn",
                bucket=bucket.id,
                lambda_functions=funct_args,
                opts=localopts,
            )
