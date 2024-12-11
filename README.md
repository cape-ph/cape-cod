# CAPE Cod

[![CI/CD](https://github.com/cape-ph/cape-cod/actions/workflows/cape.yml/badge.svg)](https://github.com/cape-ph/cape-cod/actions/workflows/cape.yml)

Welcome to the home of the Center For Applied Pathogen Genomics (_and Outbreak
Control_) Pulumi IaC (Infrastructure as Code).

## 🧬 Features

**NOTE:** Any of the below features can change at any time. This whole system is
a work in progress.

The CAPE infrastructure currently consists of:

-   A system-wide object store for reusable ETL scripts and Lambda functions
    (this is currently used to prime the system and may not always be around).
-   A data lake for any number of configurable domains (called `Tributaries`)
    which have their own raw and clean object storage and feed the lake over all
    via shared data catalog.
-   More to come

## 🦠 Requirements

-   [Python 3.10+](https://www.python.org/)
-   [Pulumi](https://www.pulumi.com/)
-   [AWS CLI](https://aws.amazon.com/cli/)
-   An AWS account with the ability to create most resources. We're actively
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

Our [public development config file](./Pulumi.cape-cod-dev.yaml) contains
documentation and examples for every available config option we support. Please
refer to this file when configuring your deployment.

### Secret Asset Management

**_WIP_** Managing a deployment of a system such as this requires management of
files that should never end up in revision control. Eaxmples include TLS related
files (e.g. private keys) and EC2 instance bootstrap scripts that may expose
sensitive information. The CAPE infrastructure repo is configured with a
`.gitignore` of the directory `<repo_root>/assets-untracked` in order to give
the most basic form of protection to these assets. This may not be the best way
for you and your deployment to manage it, but it is available. This is covered
in some detail in the VPN README referenced in the
[Additional Documentation](#-additional-documentation) section below.

## 📐 Additional Documentation

-   [Debug VPN Deployment/Setup](./extra-doc/README.vpn.md)
-   [Writeup of some queuing considerations](./extra-doc/README.queuing.md)

## 🗒️ Links

## 🥼 Contributing

If you plan to contribute, please check the
[contribution guidelines](https://github.com/cape-ph/.github/blob/main/CONTRIBUTING.md)
first.

<!--Reference links follow...-->

[awscron]:
    https://docs.aws.amazon.com/glue/latest/dg/monitor-data-warehouse-schedule.html
[awscrawlerpaths]:
    https://docs.aws.amazon.com/glue/latest/dg/define-crawler.html#define-crawler-choose-data-sources
