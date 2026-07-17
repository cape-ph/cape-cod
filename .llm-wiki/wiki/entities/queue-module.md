---
type: entity
title: "queue module (capeinfra/resources/queue.py)"
slug: queue-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["sqs", "queue", "resources"]
---

# queue module (`capeinfra/resources/queue.py`)

## `SQSQueue(CapeComponentResource)`

- `type_name` = `capeinfra:resources:queue:SQSQueue`.
- `PolicyEnum`: `put_msg` (`sqs:GetQueueUrl`, `sqs:SendMessage`) and
  `consume_msg` (`sqs:GetQueueAttributes`, `sqs:ReceiveMessage`,
  `sqs:DeleteMessage`).
- Constructor creates a FIFO queue: `aws.sqs.Queue` with `fifo_queue=True`,
  `content_based_deduplication=True`, and a `.fifo` name suffix. Registers
  `queue_name` as an output.
- `policies` lazily builds the two statement groups above for use with
  [[entities/iam-module]] role helpers.

Used as the notification target for data lake source-bucket events, which then
fan out to ETL trigger Lambdas (see [[entities/datalake-module]] and
[[syntheses/assets-subsystem]]). A code TODO references ISSUE #68 for the queue
resource naming.

Related: [[syntheses/resources-subsystem]],
[[concepts/capepulumi-base-classes]].
