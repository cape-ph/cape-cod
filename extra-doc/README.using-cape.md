# Using CAPE-COD

Once deployed, someone will want to use `CAPE-COD` for some purpose. This doc
gives basic usage guidance. As CAPE-COD`` itself is under early and active
development, **_this doc is a work in progress and could change at any time._**

## Getting access to the deployed CAPE-COD environment

Follow the setup instructions in [the VPN README](./README.vpn.md). Being on the
VPN is a requirement for accessing anything in the CAPE-COD environment.

## Available Routes

This section lists available routes in `CAPE-COD`. The fact that a route exists
does not mean it will be available for all users (e.g. a user that does not have
permissions to access `JupyterHub` will not be able to access it via the below
route).

### CAPE UI Routes

| Name             | Route                                              | Description                                                  |
| ---------------- | -------------------------------------------------- | ------------------------------------------------------------ |
| CAPE Pipeline UI | https://analysis-pipelines.cape-dev.org/index.html | UI for scheduling analysis pipelines (e.g. running bactopia) |

### API Routes

| Name                  | Route                            | Description                                                                                                                                                                                                                                            |
| --------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CAPE Dev DAP API Root | https://api.cape-dev.org/dap-dev | Root path for development data analysis pipeline APIs. Contains endpoints such as `analysispipelines` (GET available analysis pipelines), `pipelineexecutors` (GET available pipeline executors), and `analysispipeline` (POST to schedule a pipeline) |

### Tool Routes

| Name            | Route                            | Description                       |
| --------------- | -------------------------------- | --------------------------------- |
| CAPE JupyterHub | https://jupyterhub.cape-dev.org/ | URL To access JupyterHub for CAPE |

## Admin User Use Cases

### Deployment

**_TBD_**

### Adding Users

**_TBD_**

### Adding New ETL

**_TBD_**

### [Re]Deployment Known Issues

#### Manual API Redeployment

After re-deploying CAPE (e.g. deploying a new feature or environment change), if
any changes are made that affect networking, load balancers or an API gateway,
you may see something like the following when attempting to hit an API:

```
{
    "Message":
        "User: anonymous is not authorized to perform: execute-api:Invoke on resource:
        arn:aws:execute-api:us-east-2:************:jfta1swfk9/dap-dev/GET/analysispipelines 1
        with an explicit deny"
}
```

If encountered go the to the AWS console page for the API gateway and manually
re-deploy the API in question. This will often solve the issue until the next
deployment.

## General User Use Cases
