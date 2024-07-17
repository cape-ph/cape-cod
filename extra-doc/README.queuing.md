# Queuing Design

- problems being solved
  - lambdas spinning (but costing) while capacity is too much
  - inability to have more than one notification on a bucket for any one event
    etc
- push
  - is all trigger-based and needs to handle requeuing on errors (e.g. over max
    concurrent runs of something)
  - minimizes cost of running lambdas when the queue is empty (at expense of
    possibly triggering more than can be handled leading to excessive trigger
    calls)
  - somewhat simpler
  - only handles one subscriber/consumer
  - re-queuing is a problem if order of processing is important (e.g. if no glue
    runs are available and there are a million items in the queue, the job that
    can't run goes to the back of the line)
- pull
  - is consume as needed
  - have to do some processing yourself to figure out if things should be
    removed from queue or left there)
  - allows for more than one subscriber (although someone needs to delete
    messages from the queue at some point)

## Push

## Pull
