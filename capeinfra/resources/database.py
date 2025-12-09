"""Module of various AWS database abstractions (e.g. DynamoDB)."""

from collections.abc import Sequence
from enum import Enum
from typing import Any

import pulumi_aws as aws
from pulumi import Output, ResourceOptions

from capepulumi import CapeComponentResource


class DynamoTable(CapeComponentResource):
    """A DynamoDB table."""

    class PolicyEnum(str, Enum):
        """Enum of supported policy names for this component."""

        read = "read"

    def __init__(
        self,
        name,
        hash_key: str,
        range_key: str,
        idx_attrs: Sequence[aws.dynamodb.TableAttributeArgs],
        **kwargs,
    ):

        # This maintains parental relationships within the pulumi stack
        super().__init__(
            "capeinfra:resources:database:DynamoTable",
            name,
            **kwargs,
        )

        self.name = name

        self.ddb_table = aws.dynamodb.Table(
            f"{self.name}-ddbt",
            name=f"{self.name}-DDBT",
            # NOTE: Eventually we'll want to get a handle on the usage of all
            #       our DDB tables so we can consider moving to "PROVISIONED"
            #       instead of "PAY_PER_REQUEST". We'd probably be much
            #       cheaper to go that route if we have a really solid idea of
            #       how many reads/writes each table needs. at that point we'll
            #       want to be able to set this via params in the `DynamoTable`
            #       caonstructor
            billing_mode="PAY_PER_REQUEST",
            hash_key=hash_key,
            range_key=range_key,
            attributes=idx_attrs,
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (f"{self.desc_name} DynamoDB Table"),
            },
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"dynamo_table_name": self.ddb_table.name})

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
            self.policies[self.PolicyEnum.read] = [
                {
                    "effect": "Allow",
                    "actions": [
                        "dynamodb:DescribeTable",
                        "dynamodb:GetItem",
                        # TODO: arguably we don't need to include scan here.
                        #       scan reads the whole table (or a bunch of the
                        #       table) at once. we grant it currently for the
                        #       API endpoints that need it, but that's the
                        #       only place we grant it.
                        "dynamodb:Scan",
                    ],
                }
            ]
        return self._policies

    def add_table_item(self, name: str, item: dict[str, dict[str, Any]]):
        """Add an item to the table.

        For more information on DynamoDB Attribute Value format, see here:
        https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_AttributeValue.html

        Args:
            name: A name for the item. This will be part of the full AWS
                  resource name and should be kept as short as possible.
            item: A dict representing the item to add. The values of the dict
                  *must* themselves be dicts in the DynamoDB attribute format
                  and the values of the subdicts may contain Pulumi Output
                  values.
        """

        aws.dynamodb.TableItem(
            f"{self.name}-{name}-ddbitem",
            table_name=self.ddb_table.name,
            hash_key=self.ddb_table.hash_key,
            range_key=self.ddb_table.range_key.apply(lambda rk: f"{rk}"),
            item=Output.json_dumps(item),
            opts=ResourceOptions(parent=self),
        )
