# CAPE Cod

Welcome to the home of the Center For Applied Pathogen Genomics (_and Outbreak
Control_) Pulumi IaC (Infrastructure as Code).

## 🧬 Features

**NOTE:** Any of the below features can change at any time. This whole system is
a work in progress.

The CAPE infrastructure currently consists of:

- A system-wide object store for reusable ETL scripts and Lambda functions (this
  is currently used to prime the system and may not always be around).
- A data lake for any number of configurable domains (called `Tributaries`)
  which have their own raw and clean object storage and feed the lake over all
  via shared data catalog.
- More to come

## 🦠 Requirements

- [Python 3.10+](https://www.python.org/)
- [Pulumi](https://www.pulumi.com/)
- [AWS CLI](https://aws.amazon.com/cli/)
- An AWS account with the ability to create most resources. We're actively
  adding more as we go and just having the ability to create what we currently
  use may not be the full list in the long term.

## 🧫 Setup

Install [python](https://www.python.org/downloads/) and
[pulumi](https://www.pulumi.com/docs/install/) according to their instructions.

**_NOTE:_** Usage of the term `stack` is overloaded by `pulumi` and some
providers. E.g. a stack in AWS is often used in the context of `CloudFormation`.
For the purposes of this document, if `stack` is used with no other qualifier,
we are talking about a `pulumi` stack.

Pulumi uses the currently configured (by the aws cli) AWS credentials. There are
a number of ways to do this that are dependent on how your AWS account is set
up. See
[the pulumi docs on the subject](https://www.pulumi.com/registry/packages/aws/installation-configuration/)
for info on how to setup. The rest of this section assumes this has been done.

Open a terminal, clone this repo and `cd` to the root.

Begin by executing

```shell
pulumi login --local
```

This will log you into the local backend (all pulumi state is managed on the
local filesystem). There are a number of ways to manage pulumi state (such as a
shared object store for a development team), so if you need something different
than state on the local filesystem, consider
[the other supported options](https://www.pulumi.com/docs/cli/commands/pulumi_login/).

Now we need to initialize a stack state in the backend that has been logged
into. Execute the following

```shell
pulumi stack init cape-cod-public
```

This will setup the `pulumi` state for our public stack. At this point we need a
disclaimer...

**This stack should only be used for informational purposes and is in no way
secure. If you wish to use the public stack as a start for your own stack with
your own encryption key, see the
[Extending The cape-cod Stack](#extending-the-cape-cod-stack) section below.
There are no encrypted values in this stack by design, and values that should be
encrypted will start with an unencrypted value of SET_SECRET. Any SET_SECRET
values will likely need to be set before this stack can be deployed.**

At this point you should have a new stack in your state. This can be verified
with

```shell
pulumi stack ls
```

The new stack should be listed, and have an asterisk next to it denoting it is
the active stack. If the stack is listed but not active, execute

```shell
pulumi stack select cape-cod-public
```

This will make the public version of our dev stack active.

The encryption key for this stack is `insecure`. This will be needed for the a
number of `pulumi` commands.

We need to make sure there are no values in the config that are in need of
setting before we can deploy. So execute

```shell
grep -i set_secret Pulumi.cape-cod-public.yaml
```

If any results are returned, these keys should be set to values that make sense
for your circumstances. See the [Config Values](#config-values) table below for
hints on what values are expected.

**_NOTE:_** This config will change over time, and as you pull upstream changes
into your clone new secret config keys may be added. You should get ion the
habit of checking for new secret values on every pull.

If encrypted values do in fact need to be set, this can be accomplished with

```shell
pulumi config set --secret <key> <unencrypted_value>
```

You'll be prompted for the encryption key, and upon completion the encrypted
value will be inserted into your local `Pulumi.cape-cod-public.yaml` file. For
more on setting config values in the pulumi config files, see
[Pulumi's config documentation](https://www.pulumi.com/docs/concepts/config/)

Next, to ensure everything is working as expected and to create the python venv
used by pulumi, execute

```shell
pulumi preview
```

You will be prompted for the encryption key. Provide it and hit `<Enter>`. This
should complete with no errors and give you an indication of the number of
resources that will be created when the stack is deployed (as well as their
names and hierarchy).

If there are no errors, the stack should be deployable assuming the AWS account
is permissive enough and the user performing the deployment has authorization
for all operations.

## 🔬 Usage/Deployment

### Extending the cape-cod Stack

To make your own stack with a secure encryption key and to set your own config
values, execute the following

```shell
pulumi stack init [stack-name] --copy-config-from cape-cod-public
```

**_NOTE:_** This will set the new stack as the active one, so any config changes
you make or deployments/previews will apply to the new stack. If you do not wish
to immediately select your new stack, pass `--no-select` to the command.

You will be asked to provide an encryption key for the new stack (and to confirm
it again).

**_NOTE:_** Be sure to manage this key in a secure manner as it will be needed
for nearly all future pulumi actions for this stack.

You will then be prompted for the original stack's encryption key in order to
decrypt any secret values so they can be re-encrypted with the new encryption
key when copied over. On completion, you will have a new stack that is a copy of
the public stack with your new encryption key.

### Config Values

This section contains information about the set of config values available in
the `pulumi` configuration.

In the following table, nested keys are given in dotted notation. E.g. the
name/key `cape-cod:meta.glue.etl.name` would map to `<THIS VALUE>` in the
following YAML

```yaml
cape-cod:meta:
    glue:
        etl:
            - name: <THIS VALUE>
```

Some dotted names contain items such as `[something|something_else]`. In these
cases both `something` and `something_else` are valid, though they are
different. E.g. in the case of
`cape-cod:datalakehouse.tributaries.buckets.[raw|clean]`, there are keys for
both `cape-cod:datalakehouse.tributaries.buckets.raw` and
`cape-cod:datalakehouse.tributaries.buckets.clean`, and the keys apply to
different bucket configs.

If a key is marked as optional but a lower level key is marked as required, this
implies that if provided, the lower level key is required if the higher key is
provided. E.g. `cape-cod:meta.glue.etl` is optional, but if any items are
defined in that sequence, the key `cape-cod:meta.glue.etl.name` is required for
each item.

| name                                                                          | required?    | secret? | data format | description                                                                                                                                                                                                                                                              |
| ----------------------------------------------------------------------------- | ------------ | ------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `cape-cod:meta`                                                               | **required** | no      | `mapping`   | Contains configuration that is used by a number of functional areas in the deployment. E.g. a common s3 bucket where ETL scripts and Lambda functions can be found.                                                                                                      |
| `cape-cod:meta.glue`                                                          | _optional_   | no      | `mapping`   | Contains meta configuration related to aws glue.                                                                                                                                                                                                                         |
| `cape-cod:meta.glue.etl`                                                      | _optional_   | no      | `mapping[]` | Contains meta configuration related to aws glue etl scripts.                                                                                                                                                                                                             |
| `cape-cod:meta.glue.etl.name`                                                 | **required** | no      | `string`    | The name of the etl script. This will be used as part of the object name in storage as well as part of the name in the pulumi state.                                                                                                                                     |
| `cape-cod:meta.glue.etl.key`                                                  | **required** | no      | `string`    | The key to use when placing this script in object storage. This should include any required prefixes.                                                                                                                                                                    |
| `cape-cod:meta.glue.etl.srcpth`                                               | **required** | no      | `string`    | The source path of this script if copying from the deployment repo. **This key may become optional or be removed all together in the future. Ideally we will not have ETL scripts in this repo in the long run but rather have them pulled/pushed from other repos.**    |
| `cape-cod:datalakehouse`                                                      | **required** | no      | `mapping`   | Contains configuration specific to the data lake house. The data lake house will have some common elements regardless of tributary config (e.g. data catalog, athena workgroup, etc).                                                                                    |
| `cape-cod:datalakehouse.tributaries`                                          | _optional_   | no      | `mapping[]` | Contains configuration specific to a specific domain in the data lake house (e.g. HAI). Each tributary has its own raw/clean storage, etl scripts, lambda functions, etc.                                                                                                |
| `cape-cod:datalakehouse.tributaries.name`                                     | **required** | no      | `string`    | The name of the tributary. This will be used as the base for a number of resource names and as a name in the pulumi state.                                                                                                                                               |
| `cape-cod:datalakehouse.tributaries.buckets`                                  | _optional_   | no      | `mapping`   | A mapping of bucket config for the tributary.                                                                                                                                                                                                                            |
| `cape-cod:datalakehouse.tributaries.buckets.[raw\|clean]`                     | _optional_   | no      | `mapping`   | A mapping of config for the raw/clean bucket for the tributary.                                                                                                                                                                                                          |
| `cape-cod:datalakehouse.tributaries.buckets.[raw\|clean].name`                | _optional_   | no      | `string`    | A name for the raw/clean bucket. If not provided a sensible default will be used.                                                                                                                                                                                        |
| `cape-cod:datalakehouse.tributaries.buckets.[raw\|clean].crawler`             | _optional_   | no      | `mapping`   | Crawler config for the raw/clean bucket. Only needed if a crawler is needed for the raw bucket.                                                                                                                                                                          |
| `cape-cod:datalakehouse.tributaries.buckets.[raw\|clean].crawler.classifiers` | _optional_   | no      | `string[]`  | A list of custom classifiers for the crawler. If not provided the AWS schema detection will be allowed to figure out what to use (which may not be possible depending on the raw data schema). These classifiers must exist either in AWS or as part of this deployment. |
| `cape-cod:datalakehouse.tributaries.pipelines`                                | _optional_   | no      | `mapping`   | Mapping of pipeline config for the tributary. We support different types of pipelines (e.g. data and analysis).                                                                                                                                                          |
| `cape-cod:datalakehouse.tributaries.pipelines.data`                           | _optional_   | no      | `mapping`   | Mapping of data pipeline config for the tributary.                                                                                                                                                                                                                       |
| `cape-cod:datalakehouse.tributaries.pipelines.data.etl`                       | _optional_   | no      | `mapping[]` | List of ETL (data pipeline) config mappings for the tributary.                                                                                                                                                                                                           |
| `cape-cod:datalakehouse.tributaries.pipelines.data.etl.name`                  | **required** | no      | `string`    | A name for the ETL data pipeline. This will be used as the base for a number of resources as well as a base for names in the pulumi state.                                                                                                                               |
| `cape-cod:datalakehouse.tributaries.pipelines.data.etl.script`                | **required** | no      | `string`    | The key for the script in the meta assets bucket (including any prefixes).                                                                                                                                                                                               |
| `cape-cod:datalakehouse.tributaries.pipelines.data.etl.prefix`                | **required** | no      | `string`    | Any prefix in the raw bucket to limit the ETL to. The key may contain an empty value for no prefixes.                                                                                                                                                                    |
| `cape-cod:datalakehouse.tributaries.pipelines.data.etl.suffixes`              | **required** | no      | `string[]`  | A list of suffixes to limit the ETL to. All suffixes will be passed through ETL if the list is empty.                                                                                                                                                                    |
| `cape-cod:datalakehouse.tributaries.pipelines.data.etl.pymodules`             | **required** | no      | `string[]`  | A list of python modules (using [PEP 440](https://peps.python.org/pep-0440/) version specification if needed) to ensure are available for the ETL script. **NOTE** these will be installed as the ETL script is spun up, increasing execution time and monetary cost.    |

## 🗒️ Links

## 🥼 Contributing

If you plan to contribute, please check the
[contribution guidelines](https://github.com/cape-ph/.github/blob/main/CONTRIBUTING.md)
first.
