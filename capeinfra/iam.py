"""Identity and access management constructs.

Helpfully, the big three cloud providers all use this term.
"""

import json
from typing import List

import pulumi_aws as aws
from pulumi import Input, Output, ResourceOptions

# TODO: ISSUE #72


def get_service_assume_role(srvc: str | List[str]) -> str:
    """Get a role policy statement for assuming a given AWS service.

    Args:
        srvc: The name of the service assuming the role (e.g.
              "glue.amazonaws.com") or a list of such service names.

    Returns:
        The policy statement as a json encoded string.
    """

    # make sure our assume service(s) exists in a list
    assume_trusts = [srvc] if isinstance(srvc, str) else srvc

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": assume_trusts},
                    "Action": "sts:AssumeRole",
                }
            ],
        },
    )


# TODO: need to lock this down to CAPE buckets, our account, etc
def get_s3_api_proxy_policy(
    principal: str | None = None,
) -> str:
    """Get a role policy statement for Get/List perms on s3 buckets.

    Args:

    Returns:
        The policy statement as a json encoded string.
    """
    policy_dict = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    # api for MPU
                    # NOTE: not adding UploadPart at this time. using presigned
                    #       urls and not sure at this point if UploadPart is
                    #       required in that case
                    "s3:AbortMultipartUpload",
                    "s3:CreateMultipartUpload",
                    "s3:CompleteMultipartUpload",
                    "s3:ListParts",
                    "s3:ListMultipartUploads",
                    # general s3 actions needed by api
                    "s3:PutObject",
                    "s3:DeleteObject",
                ],
                "Resource": [
                    f"arn:aws:s3:::*/*",
                    f"arn:aws:s3:::*",
                ],
            }
        ],
    }

    if principal is not None:
        for stmnt in policy_dict["Statement"]:
            stmnt.setdefault("Principal", principal)

    return json.dumps(policy_dict)


def get_bucket_reader_policy(
    buckets: aws.s3.BucketV2 | list[aws.s3.BucketV2],
    principal: str | None = None,
) -> str:
    """Get a role policy statement for Get/List perms on s3 buckets.

    Args:
        buckets: A BucketV2 object or a list of BucketV2 objects to grant
                 Get/List permissions to.
        principal: The principal the policy applies to. In the case of service
                   roles (e.g. the policy is in an inline role attached to a
                   glue crawler role), this isn't needed.

    Returns:
        The policy statement as a json encoded string.
    """
    buckets = [buckets] if isinstance(buckets, aws.s3.BucketV2) else buckets
    policy_dict = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{bucket}/*",
                    f"arn:aws:s3:::{bucket}",
                ],
            }
            for bucket in buckets
        ],
    }

    if principal is not None:
        for stmnt in policy_dict["Statement"]:
            stmnt.setdefault("Principal", principal)

    return json.dumps(policy_dict)


def get_bucket_web_host_policy(
    buckets: aws.s3.BucketV2 | list[aws.s3.BucketV2],
    vpce_id: Input[str] | None = None,
) -> Output[str]:
    """Get a role policy statement for Get perm on s3 buckets.

    This statement also allows an optional VPC id to limit access to. If not
    specified, this will result in no VPC restriction

    Args:
        buckets: A BucketV2 object or a list of BucketV2 objects to grant
                 Get/List permissions to.
        vpce_id: An optional VPC Endpoint id to limit access to.

    Returns:
        The policy statement as a json encoded string.
    """
    buckets = [buckets] if isinstance(buckets, aws.s3.BucketV2) else buckets

    stmnts = [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Principal": "*",
            "Resource": [
                # NOTE: because this is used in Output.json_dumps below, we need
                #       to do these as output.apply instead of just using
                #       `bucket` as done in some other functions in this module
                bucket.bucket.apply(lambda b: f"arn:aws:s3:::{b}/*"),
                bucket.bucket.apply(lambda b: f"arn:aws:s3:::{b}"),
            ],
        }
        for bucket in buckets
    ]

    # TODO: This would be a ton cleaner using aws.iam.get_policy_document
    #       which has arguments for all of these things (resources, conditions,
    #       etc). We should consider switching this module to use that instead
    #       of dumping our own manual json dicts
    if vpce_id:
        for d in stmnts:
            d.update(
                {"Condition": {"StringEquals": {"aws:SourceVpce": vpce_id}}}
            )

    return Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": stmnts,
        },
    )


# TODO: this allows invoke access to *all* apis in the VPC as long as traffic
# comes through the VPC endpoint. W probably want to lock this down to specific
# APIs as an argument here.
def get_vpce_api_invoke_policy(
    vpc_id: Input[str] | None = None,
    vpce_id: Input[str] | None = None,
) -> Output[str]:
    """Get a role policy statement for VPC endpoint limited execute-api:Invoke.

    NOTE:
        - At present, this allows invoke access to *all* APIs in the VPC if
          coming from the given VPC or VPC endpoint.
        - Do not specify both vpc_id and vpce_id. This will raise a ValueError.

    Args:
        vpc_id: An optional VPC id to limit invoke access to. This is
                appropriate for setting up invoke access policies for a vpc
                endpoint.
        vpce_id: An optional VPC Endpoint id to limit invoke access to. This is
                 appropriate for setting up invoke access policies for things
                 that should only be accessed through a VPC endpoint.

    Returns:
        The policy statement as a json encoded string.

    Raises:
        ValueError: If both vpc_id and vpce_id are specified.
    """
    if None not in (vpc_id, vpce_id):
        raise ValueError(
            "Cannot specify both a VPC id and a VPCE id for an api invoke "
            "policy"
        )

    stmnts = [
        {
            "Effect": "Allow",
            "Principal": "*",
            "Action": "execute-api:Invoke",
            "Resource": ["arn:aws:execute-api:*:*:*"],
        }
    ]

    if vpc_id is not None:
        stmnts.append(
            {
                "Effect": "Deny",
                "Principal": "*",
                "Action": "execute-api:Invoke",
                "Resource": ["arn:aws:execute-api:*:*:*"],
                "Condition": {"StringNotEquals": {"aws:SourceVpc": vpc_id}},
            }
        )

    if vpce_id is not None:
        stmnts.append(
            {
                "Effect": "Deny",
                "Principal": "*",
                "Action": "execute-api:Invoke",
                "Resource": ["arn:aws:execute-api:*:*:*"],
                "Condition": {"StringNotEquals": {"aws:SourceVpce": vpce_id}},
            }
        )

    return Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": stmnts,
        }
    )


def get_start_crawler_policy(crawler: str) -> str:
    """Get a role policy statement for starting a crawler.

    Args:
        crawler: The name of the crawler to start

    Returns:
        The policy statement as a json encoded string.
    """

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "glue:StartCrawler",
                        "glue:GetCrawler",
                    ],
                    "Resource": [f"arn:aws:glue:*:*:crawler/{crawler}"],
                },
            ],
        },
    )


def get_nextflow_executor_policy() -> str:
    """Get a role policy statement for an EC2 instance of Nextflow.

    Returns:
        The policy statement as a json encoded string.
    """

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "batch:CancelJob",
                        "batch:DescribeComputeEnvironments",
                        "batch:DescribeJobDefinitions",
                        "batch:DescribeJobQueues",
                        "batch:DescribeJobs",
                        "batch:ListJobs",
                        "batch:RegisterJobDefinition",
                        "batch:SubmitJob",
                        "batch:TagResource",
                        "batch:TerminateJob",
                        "ec2:DescribeInstanceAttribute",
                        "ec2:DescribeInstanceStatus",
                        "ec2:DescribeInstanceTypes",
                        "ec2:DescribeInstances",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:BatchGetImage",
                        "ecr:DescribeImageScanFindings",
                        "ecr:DescribeImages",
                        "ecr:DescribeRepositories",
                        "ecr:GetAuthorizationToken",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:GetLifecyclePolicy",
                        "ecr:GetLifecyclePolicyPreview",
                        "ecr:GetRepositoryPolicy",
                        "ecr:ListImages",
                        "ecr:ListTagsForResource",
                        "ecs:DescribeContainerInstances",
                        "ecs:DescribeTasks",
                        "logs:GetLogEvents",
                        "s3:*",
                    ],
                    "Resource": ["*"],
                },
            ],
        },
    )


def get_start_etl_job_policy(job: str) -> str:
    """Get a role policy statement for starting an ETL job.

    Args:
        job: The name of the job being started.

    Returns:
        The policy statement as a json encoded string.
    """

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "glue:StartJobRun",
                        "glue:GetJobRun",
                    ],
                    "Resource": [f"arn:aws:glue:*:*:job/{job}"],
                },
            ],
        },
    )


def get_etl_job_s3_policy(
    raw_bucket: str,
    clean_bucket: str,
    script_bucket: str,
    script_path: str,
    assets_bucket: str | None = None,
) -> str:
    """Get a role policy statement for an ETL job to read/write to s3.

    Needed to read from a clean bucket and the bucket containing the ETL script
    as well as to write to the clean bucket.

    Args:
        raw_bucket: The name of the raw bucket.
        clean_bucket: The name of the clean bucket.
        script_bucket: The name of the script bucket.
        script_path: The path to the ETL script in the script bucket.

    Returns:
        The policy statement as a dictionary json encoded string.
    """

    # TODO: FIX THE INCLUSION OF THE ASSETS BUCKET IN THESE PERMISSIONS
    statements = [
        {
            "Effect": "Allow",
            "Action": [
                "logs:PutLogEvents",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
            ],
            "Resource": "arn:aws:logs:*:*:*",
        },
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": [
                f"arn:aws:s3:::{script_bucket}/{script_path}",
                f"arn:aws:s3:::{raw_bucket}/*",
                f"arn:aws:s3:::{raw_bucket}",
                f"arn:aws:s3:::{assets_bucket}/*",
                f"arn:aws:s3:::{assets_bucket}",
            ],
        },
        {
            "Effect": "Allow",
            "Action": ["s3:PutObject"],
            "Resource": [
                f"arn:aws:s3:::{clean_bucket}/*",
                f"arn:aws:s3:::{clean_bucket}",
            ],
        },
    ]

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": statements,
        },
    )


# TODO: ISSUE #152 this is now used for a couple of different notifiers, with
#       and without attributes tables. the param names are a little specific to
#       one use case only and there is a world in which we need to add other
#       statements optionally (other than for an dynamodb table). refactor?
def get_sqs_notifier_policy(
    queue_name: str, etl_attr_ddb_table_name: str | None = None
) -> str:
    """Get a role policy statement for reading dynamodb and writing sqs.

    This policy allows for actions on an sqs queue, (optionally) a dynamodb
    table and logging necessary for raw data handlers to place metadata about
    a new S3 object into a specific SQS queue (and to read some of the metadata
    from a dynamodb table if configured).

    Args:
        queue_name: the name of the queue to grant access to.
        etl_attr_ddb_table_name: The optional name of the DynamoDB table
                                 storing the ETL attributes.

    Returns:
        The policy statement as a dictionary json encoded string.
    """
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:PutLogEvents",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                ],
                "Resource": "arn:aws:logs:*:*:*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sqs:GetQueueUrl",
                    "sqs:SendMessage",
                ],
                "Resource": [
                    f"arn:aws:sqs:*:*:{queue_name}",
                ],
            },
        ],
    }

    if etl_attr_ddb_table_name:
        policy["Statement"].append(
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:DescribeTable",
                    "dynamodb:GetItem",
                ],
                "Resource": [
                    f"arn:aws:dynamodb:*:*:table/{etl_attr_ddb_table_name}",
                ],
            }
        )
    return json.dumps(policy)


# TODO: ISSUE #TBD trying to get this a little more generalized than when it
#       only existed for the DAP api (which needed the table/queue access this
#       function currently gives). It'd be great if this was totally
#       configurable for any resource grant, but it would also be great if we
#       didn't have to give the same access to every function in the API. Until
#       we do a little more design and have another API using this, not going to
#       spend too long getting it perfect. Also, we should restrict the EC2
#       instance describing
# TODO: ISSUE 245 - TOO MANY PERMS HERE
def get_api_policy(grants: dict[str, list[Output]]):
    """Get a role policy statement for the API.

    The entire API (all functions) will be given access as configured in
    `grants`. Lambda logging will be enabled without configuration as will the
    ability to describe EC2 instances. Other
    configurable access we currently we handle:
    * DDB tables (lambdas given describe and scan access)
    * SQS queues (lambdas given get queue url and send message access)


    Args:
        grants: A dict of the format:
            {
               "table": [name Output for DDB table resources],
               "queue": [name Output for SQS queue resources],
            }

    Returns:
        The policy statement as a dictionary json encoded string.
    """
    stmnts = [
        {
            "Effect": "Allow",
            "Action": [
                "logs:PutLogEvents",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
            ],
            "Resource": "arn:aws:logs:*:*:*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
            ],
            "Resource": [
                "*",
            ],
        },
        {
            "Effect": "Allow",
            "Action": ["s3:ListBucket", "s3:ListAllMyBuckets", "s3:PutObject"],
            "Resource": [
                "*",
            ],
        },
    ]

    # add the queue grants as configured
    for q in grants.get("queue", []):
        stmnts.append(
            {
                "Effect": "Allow",
                "Action": [
                    "sqs:GetQueueUrl",
                    "sqs:SendMessage",
                ],
                "Resource": [
                    f"arn:aws:sqs:*:*:{q}",
                ],
            },
        )

    # add the table grants as configured
    for t in grants.get("table", []):
        stmnts.append(
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:DescribeTable",
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                ],
                "Resource": [
                    f"arn:aws:dynamodb:*:*:table/{t}",
                ],
            },
        )

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": stmnts,
        },
    )


# TODO: grants doesn't do anything here yet. Not sure what we'll add access to
#       at this point
def get_api_lambda_authorizer_policy(funct_arns: list[Output] | None = None):
    """Get a role policy statement for the an API Lambda Authorizer.

    The authorizer for an API will be given access as configured in
    `grants`. Lambda logging will be unconditionally enabled without
    configuration.

    At present, `grants` is a placeholder and cannot be used to modify the
    policy. This will change as the needs of the authorizers matures.


    Args:
        funct_arns: A list of lambda ARN Outputs

    Returns:
        The policy statement as a dictionary json encoded string.
    """
    stmnts = [
        {
            "Effect": "Allow",
            "Action": [
                "logs:PutLogEvents",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
            ],
            "Resource": "arn:aws:logs:*:*:*",
        },
    ]

    # TODO: figure out what the authorizer actually needs grants on

    # add the table grants as configured
    for fa in funct_arns or []:
        stmnts.append(
            {
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction",
                ],
                "Resource": [f"{fa}"],
            },
        )

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": stmnts,
        },
    )


def get_sqs_lambda_glue_trigger_policy(queue_name: str, job_names: list) -> str:
    """Get a role policy statement for reading from sqs and starting glue jobs.

    This policy allows for actions on an sqs queue, configured glue jobs and
    logging necessary for SQS trigger functions to read metadata from an SQS
    queue and to start ETL glue jobs with the metadata.

    Args:
        queue_name: the name of the queue to grant access to.
        job_names: a list of ETL job names that this policy will allow execution
                   of.

    Returns:
        The policy statement as a dictionary json encoded string.
    """

    statements = [
        {
            "Effect": "Allow",
            "Action": [
                "logs:PutLogEvents",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
            ],
            "Resource": "arn:aws:logs:*:*:*",
        },
        {
            "Effect": "Allow",
            "Action": [
                # This is the bare minimum required for an SQS notified
                # lambda to do its job.
                "sqs:GetQueueAttributes",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
            ],
            "Resource": [
                f"arn:aws:sqs:*:*:{queue_name}",
            ],
        },
    ]

    # generally we will have job names here (otherwise whey put in a job queue)
    # but if they have not been defined at the time of the tributary deployemnt,
    # we may not. so only add the policy for them if we have some listed.
    if job_names:
        statements.append(
            {
                "Effect": "Allow",
                "Action": [
                    "glue:StartJobRun",
                    "glue:GetJobRun",
                ],
                "Resource": [
                    f"arn:aws:glue:*:*:job/{job}" for job in job_names
                ],
            }
        )
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": statements,
        },
    )


# NOTE: done as a function for now because this pattern is in a number of
#       places (lambda trigger functions, data crawlers, glue jobs, etc)
def get_inline_role(
    name: str,
    desc_name: str,
    srvc_prfx: str,
    assume_role_srvc: str | List[str],
    role_policy: Input[str] | None = None,
    srvc_policy_attach: str | List[str] = [],
    opts: ResourceOptions | None = None,
) -> aws.iam.Role:
    """Get an inline role fir the given arguments.

    Args:
        name: The resource name the role is being used on.
        desc_name: The descriptive name (e.g. for tagging) for the role. this
                   will be used as-is, so it needs to be fully rendered
        srvc_prfx: the service prefix to use in the name (e.g. `lmbd` for aws
                   lambda)
        assume_role_srvc: The name of the service assuming the role (e.g.
                          "glue.amazonaws.com") or a list of such service names.
        role_policy: The policy to attach to the role.
        srvc_policy_attach: Optional identifier (e.g. ARN for aws) or list of
                            identifiers for a service or services role policy
                            to attach to the role in addition to the
                            role_policy. NOTE: There is an AWS imposed maximum
                            of 20 policy attachments for any role.
        opts: The pulumi ResourceOptions to add to ComponentResources created
              here.

    Returns:
        The inline role.
    """
    policy_attachments = (
        [srvc_policy_attach]
        if isinstance(srvc_policy_attach, str)
        else srvc_policy_attach
    )

    # first create the inline role
    inline_role = aws.iam.Role(
        f"{name}-{srvc_prfx}role",
        assume_role_policy=get_service_assume_role(assume_role_srvc),
        opts=opts,
        tags={"desc_name": desc_name},
    )

    # if we were told to also attach service role policies, do so
    if policy_attachments:
        for policy_arn in policy_attachments:
            aws.iam.RolePolicyAttachment(
                f"{name}-{srvc_prfx}svcroleatch-{policy_arn.split('/')[-1]}",
                role=inline_role.name,
                policy_arn=policy_arn,
                opts=opts,
            )

    # and now add the policy rules we were given to the role if configured
    if role_policy is not None:
        aws.iam.RolePolicy(
            f"{name}-{srvc_prfx}roleplcy",
            role=inline_role.id,
            policy=role_policy,
            opts=opts,
        )

    return inline_role


def get_instance_profile(
    name: str,
    role: aws.iam.Role,
    name_suffix: str | None = None,
) -> aws.iam.InstanceProfile:
    """Get an instance profile for the given role

    Args:
        role: The role in which to generate an instance profile for

    Returns:
        The instance profile
    """
    return aws.iam.InstanceProfile(
        f"{name}-instnc-prfl{('-'+ name_suffix) if name_suffix else ''}",
        role=role.name,
        opts=ResourceOptions(parent=role),
    )


def get_sqs_lambda_dap_submit_policy(queue_name: str, table_name: str) -> str:
    """Get a role policy statement for reading dynamodb and sqs.

    This policy allows for actions on an sqs queue, a dynamodb table and
    logging necessary for data handlers to read data analysis pipeline
    submission messages from SQS as well as read the data analysis pipeline
    registry dynamodb table.

    Args:
        queue_name: The name of the queue to grant read access to.
        table_name: The name of the DynamoDB table storing the DAP
                    registry.

    Returns:
        The policy statement as a dictionary json encoded string.
    """

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:PutLogEvents",
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                    ],
                    "Resource": "arn:aws:logs:*:*:*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        # This is the bare minimum required for an SQS notified
                        # lambda to do its job.
                        "sqs:GetQueueAttributes",
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                    ],
                    "Resource": [
                        f"arn:aws:sqs:*:*:{queue_name}",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:DescribeTable",
                        "dynamodb:GetItem",
                    ],
                    "Resource": [
                        f"arn:aws:dynamodb:*:*:table/{table_name}",
                    ],
                },
                {
                    "Sid": "AllowSSMExecution",
                    "Effect": "Allow",
                    "Action": ["ssm:SendCommand", "ssm:GetCommandInvocation"],
                    # TODO: get this specified via parameter
                    "Resource": [
                        # TODO: ISSUE #158 this should be changed to have
                        #       tag-based pairing down
                        "arn:aws:ec2:us-east-2:767397883306:instance/*",
                        # TODO: this isn't tied to our account
                        "arn:aws:ssm:us-east-2::document/AWS-RunShellScript",
                        # TODO: how do we lock this down better? this is needed
                        #       for GetCommandInvocation and came from an error
                        #       message, but i'm not entirely certain what exact
                        #       resource it's not allow to access
                        "arn:aws:ssm:us-east-2:767397883306:*",
                    ],
                },
                {
                    "Sid": "AllowEC2DescribeInstances",
                    "Effect": "Allow",
                    "Action": "ec2:DescribeInstances",
                    # TODO: ISSUE #158
                    "Resource": [
                        "arn:aws:ec2:*:*:instance/*",
                    ],
                    "Condition": {
                        "Null": {"aws:ResourceTag/Pipeline": "false"}
                    },
                },
            ],
        },
    )
