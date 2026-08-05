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

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:resources:queue:SQSQueue"

    def __init__(
        self, name, message_retention_seconds: int | None = None, **kwargs
    ):
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, **kwargs)

        self.name = name

        queue_kwargs = {
            "name": f"{self.name}-q.fifo",
            "content_based_deduplication": True,
            "fifo_queue": True,
            "opts": ResourceOptions(parent=self),
            "tags": {"desc_name": f"{self.desc_name} SQS queue."},
        }
        # SQS accepts 60..1209600 seconds (14 days); leaving this unset keeps
        # the SQS default of 4 days, so we only pass it through when given.
        if message_retention_seconds is not None:
            queue_kwargs["message_retention_seconds"] = (
                message_retention_seconds
            )

        self.sqs_queue = aws.sqs.Queue(
            # TODO: ISSUE #68
            f"{self.name}-q",
            **queue_kwargs,
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"queue_name": self.sqs_queue.name})

    @property
    def policies(
        self,
    ) -> dict[
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
