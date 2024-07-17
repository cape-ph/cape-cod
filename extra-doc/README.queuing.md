# Queuing Considerations

This README contains ionformation related to queuing considerations for the CAPE
infrastructure. This information is general in nature though we have different
queue considerations for different parts of the system.

Some areas in which queues are used to solve specific problems:

- Handling raw object upload prior to running ETL jobs
  - We have an indeterminant number of folks uploading an indeterminant number
    of objects at any time, but have a finite number of ETL jobs we can run at
    any time. So a queuing system makes sense so as to not lose any object
    transforms.
  - Object storage (at least in AWS S3) can only have one handler for any given
    event (e.g. ObjectCreated). While this handler can do any number of things,
    there can be only one. A topic based queuing system allows for many
    handlers.
- Submitting jobs to analytics pipelines.

  - Similarly to adding new raw objects to the system, any nyumber of users can
    submit any number of analytics pipeline jobs to the system at any time. So
    again, a queuing system makes sense here.

- Minimizing the run time of notification handlers when they are triggered
  without insufficient resources available to process. In these cases the
  handler may need to `sleep` or otherwise spin until a resource is available,
  costing money to wait.

Some items to keep in mind in the following sections:

- Putting messages in a queue can trigger a handler action. This action has a
  maximum number of concurrent instances of itself that can run. We'll refer to
  that as `max_qhandler` below.
- In the case of ETL (`glue jobs` in `AWS`), there is also a maximum number of
  concurrent instances of the ETL job. We'll refer to that as `max_etl` below.
  These jobs have some startup, run and shutdown times associated with them.
- We do not consider limiting the size of the queue in this README. At the time
  of writing, we need to handle all messages, so limiting the queue size is not
  helpful.

## Message Consumption Models

When considering the queuing system for any given problem, how the contents of
the queue are consumed is primary consideration. We consider the push and pull
consumption models below.

### Push

When we say _push_, we mean that the injection of a new message into the queue
triggers some action via a notification. In CAPE (and thus AWS), this action
will usually take the form of a Lambda function. This function may launch an ETL
job (or many) for any new object added to a raw S3 bucket, start an analysis
pipeline for some set of arguments, or something else.

#### Pros

The _push_ system minimizes the running of handlers unnecessarily as might
happen if the action was scheduled instead of triggered, and the queue was empty
for a long period. In that case the handler would run (costing money) but would
not do anything useful as there was nothing in the queue to handle. When the
action is triggered, you only run the handler when needed. So in the case of a
queue that may not contain messages all the time, _push_ may be better.

In implementation, _push_ queues are also slightly simpler when queues are small
as a one doesn't need to worry too much about figuring out if a message should
be received/deleted from the queue or throttling of any sort. This is all
handled at the trigger layer assuming resources exist to handle all the messages
in the queue.

#### Cons

There is a limit to the number of actions that can run for any particular event
(`max_qhandler`). Items kicked off by the action may also have a limit (e.g.
`max_etl`). In practice this means we need to consider the case where an action
is triggered but cannot be performed due to lack of resources.

If a queue often contains more messages than the system has resources to handle,
the _push_ system may not be ideal. In cases like this, the message being
processed by the handler will need to be removed from the queue and re-added to
cause the trigger to happen again. This adds complexity, but also costs more as
triggers that cannot be completed will still be executed via trigger.

Re-queuing may not be an issue (other than additional complexity) if order of
handling of messages is not important. This could be the case for ETL jobs when
each ETL should be independent from others. However it could be an issue in the
case of a very full queue where ETL jobs take a significant amount of time to
run. If a queue's handlers are saturated, messages causing triggers that cannot
be handled will be placed in the back of the queue in serial until handlers are
available. This means messgages that come in immediately following the
sautration may not get handled until messages that come in just after handlers
are available again.

Another potential problem with _push_ queues is that they only really handle a
single consumer of messages. The consumer may in turn kick off a number of other
actions, but like the aforementioned events on new raw objects, there can be
only one handler.

### Pull

In the _pull_ system, queue handlers are scheduled instead of being triggered on
new messages. In this case, the queue handler may be aware of how many messages
can be handled at any given time (perhaps as the result of some ad hoc
calculation) and can act accordingly. Note the number of messages that can be
handled may be 0, in which case the handler would give up until it's next
scheduled run.

#### Pros

The _pull_ system minimizes complexity of re-queuing logic and execution of
triggers that cannot complete. Re-queuing is not needed as any messages that
cannot be handled in the current instance are left on the queue for a future
run.

The _pull_ system also allows for more than one consumer of messages in the
queue. The catch is that some subscriber will need to remove the message from
the queue at some point so it isn't handled again on the next scheduled run.

#### Cons

This can be slightly more complicatd to implement as the implementor may need to
add logic to handle throttling of the message handling themselves. E.g. If
`max_etl` is 10 and there are currently 3 running when the handler is scheduled
to run, the handler would need to figure out that there are 7 handlers available
and therefore the highest number of messages it can handle is 7.

The _pull_ system is also not ideal in the case of having a queue that is only
sometimes in use. E.g. in the case of a holiday week where no one is using the
system, the scheduled handler still runs when it is scheduled to even though
there will be nothing to handle. This costs money to do no work.

## Implementation Plans

### ETL

In the case of ETL jobs, we will be using the _push_ queuing system. We are
assuming that the number of incoming raw objects will be sparse and triggering
handlers will be more appropriate than scheduling. This could change at some
point in the future when CAPE is actually in use and we can capture metrics.

### Analysis Pipelines

**_TBD_**
