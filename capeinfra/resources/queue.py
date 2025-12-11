"""Module of various AWS queue abstractions (e.g. SQS)."""

from enum import Enum

import pulumi_aws as aws
from pulumi import ResourceOptions

from capepulumi import CapeComponentResource


class SQSQueue(CapeComponentResource):
    """An SQS queue."""

    class PolicyEnum(str, Enum):
        """Enum of supported policy names for this component."""

        put_msg = "put_msg"
        consume_msg = "consume_msg"

    def __init__(self, name, **kwargs):
        # This maintains parental relationships within the pulumi stack
        super().__init__(
            "capeinfra:resources:queue:SQSQueue",
            name,
            **kwargs,
        )

        self.name = name

        self.sqs_queue = aws.sqs.Queue(
            # TODO: ISSUE #68
            f"{self.name}-q",
            name=f"{self.name}-q.fifo",
            content_based_deduplication=True,
            fifo_queue=True,
            opts=ResourceOptions(parent=self),
            tags={"desc_name": f"{self.desc_name} SQS queue."},
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"queue_name": self.sqs_queue.name})

    @property
    def policies(self) -> dict[
        str,
        list[aws.iam.GetPolicyDocumentStatementArgsDict],
    ]:
        if self._policies is None:
            self._policies = dict[
                str,
                list[aws.iam.GetPolicyDocumentStatementArgsDict],
            ]()
            self._policies[self.PolicyEnum.put_msg] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "sqs:GetQueueUrl",
                        "sqs:SendMessage",
                    ],
                }
            ]
            self._policies[self.PolicyEnum.consume_msg] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "sqs:GetQueueAttributes",
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                    ],
                }
            ]
        return self._policies
