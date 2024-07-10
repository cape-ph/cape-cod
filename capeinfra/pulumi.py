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

from .iam import get_inline_role


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

        # contains a mapping of {
        #   bucket_id: (trigger_permission, function_args[])
        # }
        # needed as some triggerables are used in unison on a single bucket
        # (e.g. many etl jobs can operate on one bucket, perhaps with different
        # prefixes) and some triggerables themselves can be used on many
        # buckets, so we need this info externally to this class to be able to
        # setup bucket notifications
        # NOTE: if we move away from bucket notifications and into something
        #       like message queues, this madness will likely become moot
        #       (though other madness may ensue)
        self.trigger_meta = {}
        # self.trigger_permission = None
        # self.trigger_function_args = []

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

    @property
    def _default_filters(self) -> list:
        """Property that returns the default empty filter for object storage.

        The default object storage filter specifies no prefix and allows all
        suffixes.

        This default filter is only used when no filters are specified in the
        configuration. If any filters are provided, this filter will not be used
        at all (unless provided manually in the configuration).

        Returns:
            A single element list containing the default object storage filter.
        """
        return [
            {
                "prefix": "",
                "suffixes": [""],
            }
        ]

    def add_trigger_function(
        self,
        script_path: str,
        role_policy: Input,
        env_vars: dict[str, typing.Any] | None,
        filters: list | None = None,
        opts: ResourceOptions | None = None,
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
        opts = opts or ResourceOptions(parent=self)

        # get a role for the trigger function
        self.trigger_role = get_inline_role(
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

        # NOTE: the permission and function args only apply if we're doing
        #       bucket notifications (e.g. triggering the function on
        #       ObjectCreated S3 event). This needs to be re-thought if we move
        #       to something like message queues.
        self._init_function_args_and_perms(filters=filters)

    def _init_function_args_and_perms(
        self,
        filters: list | None = None,
        # prefix: str | None = None,
        # suffixes: list | None = None,
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
        # perms = []
        # funct_args = []
        opts = opts or ResourceOptions(parent=self)

        filters = filters or self._default_filters
        # suffixes = suffixes or [""]
        # prefix = prefix or ""

        # Give our function permission to invoke a function for each source
        # bucket we're configured for
        for bucket in self.source_buckets:

            # make sure we're setup for holding perms and args for this bucket
            localopts = copy.copy(opts)

            localopts.depends_on = [bucket]
            self.trigger_meta.setdefault(
                bucket.id.apply(lambda i: f"{i}"), {"perms": [], "args": []}
            )

            self.trigger_meta[bucket.id.apply(lambda i: f"{i}")][
                "perms"
            ].append(
                aws.lambda_.Permission(
                    f"{self.name}-allow-{self.service_prefix}",
                    action="lambda:InvokeFunction",
                    function=self.trigger_function.arn,
                    principal="s3.amazonaws.com",
                    source_arn=bucket.arn,
                    opts=localopts,
                )
            )

            # create a set of function args for each suffix given (or a default
            # set of args if there were no suffixes given).
            for flt in filters:
                prefix = flt.get("prefix") or ""
                suffixes = flt.get("suffixes") or [""]
                for s in suffixes:
                    self.trigger_meta[bucket.id.apply(lambda i: f"{i}")][
                        "args"
                    ].append(
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
            # localopts = copy.copy(opts)
            # localopts.depends_on = perms

            # Add a bucket notification to trigger our functions automatically
            # if they were configured.
            # aws.s3.BucketNotification(
            #     f"{self.name}-s3ntfn",
            #     bucket=bucket.id,
            #     lambda_functions=funct_args,
            #     opts=localopts,
            # )
