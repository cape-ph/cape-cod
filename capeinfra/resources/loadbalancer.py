"""Module of load balancer related resources."""

import pulumi_aws as aws
from pulumi import Input, Output, ResourceOptions
from pulumi_aws.ec2.get_network_interface import get_network_interface

from capepulumi import CapeComponentResource

# NOTE:This ALB implementation supports 3 types of targets currently:
#           - static apps served from S3
#           - EC2 instance apps (EC2 instance handles everything and we just
#             forward there)
#           - apis served from api gateway
#      Multiple APIs can be served from the same subdomain FQDN (e.g.
#      api.cape-dev.org/api1 and api.cape-dev.org/api2) while static apps
#      require their own subdomain FQDN, and the bucket must be named with that
#      FQDN. Only one app can be served from any s3 bucket, and it must be
#      served from the root. Instance apps also require their own FQDN.


# Fixed response for the default action of our listeners. Anything that doesn't
# match the patterns of the listeners should get this response.
FIXED_403 = """
HTTP/1.1 403 Forbidden
Content-Type: text/html

<html>
   <head><title>403 Forbidden</title></head>
   <body>
      <h1>Forbidden</h1>
      <p>You don't have permission to access this resource.</p>
   </body>
</html>
"""


class AppLoadBalancer(CapeComponentResource):
    """Resource for an application load balancer.

    This class takes care of some supporting resources as well such as
    Listeners, Target Groups, Target Group Attachments and the ALB itself.

    NOTE: At present this class only supports one target group per listener and
          these are added via the `add_XXX_target` methods.
    """

    def __init__(
        self,
        name: str,
        vpc_id: Input[str],
        subnet_ids: list[Input[str]],
        *args,
        **kwargs,
    ):
        """Create the application load balancer.

        Args:
            name: The name of this resource.
            vpc_id: The id of the VPC to associate this ALB with.
            subnet_ids: A list of subnet ids to associate this load balancer
                        with.
            args: List of positional args that will be passed off to the
                  base class.
            kwargs: List of keyword args that will be passed off to the base
                  class.
        """
        # TODO: ISSUE #112
        super().__init__(
            "capeinfra:resources:loadbalancer:AppLoadBalancer",
            name,
            *args,
            **kwargs,
        )

        self.name = f"{name}"
        self._vpc_id = vpc_id

        # we add a number of listener rules to the load balance to handle
        # incoming requests. e.g. if we have a target EC2 based application at
        # the domain app.cape-dev.org, we'd have a listener rule for that
        # hostname that forwards traffic to that EC2 instance. each of these
        # rules have a priority. no 2 rules can have the same priority.
        # we add rules as we add targets to the load balancer, and we *do not*
        # currently have priority as configurable (nor do we have any listener
        # rule properties configurable). therefore we will just have an
        # incrementing counter for the next priority, and the prioritization of
        # rules will be based on the order in which targets are added. Adding
        # order is defined in the swimlane in which the targets are created.
        # NOTE: this does mean that if the config changes and a new target is
        #       added or an old one is remove, the the priorities (and possible
        #       resource names) of existing rules may change.
        self._rule_priority_ctr = 1

        # these will be dependent on configuration
        self._target_groups = {}
        self._listeners = {}

        # TODO: ISSUE #132
        self.alb = aws.lb.LoadBalancer(
            f"{self.name}-lb",
            internal=True,
            load_balancer_type="application",
            subnets=subnet_ids,
            tags={
                "desc_name": f"{self.desc_name}",
            },
            opts=ResourceOptions(parent=self),
        )

    @property
    def next_rule_priority(self):
        """Convenience property to get the next listener rule priority.

        Returns: The next listener rule priority value.
        """
        ret = self._rule_priority_ctr
        self._rule_priority_ctr += 1
        return ret

    def _add_target_group(
        self,
        group_id: str,
        short_name: str,
        ttype: str = "instance",
        healthcheck_args: dict | None = None,
        port: int | None = 443,
        proto: str | None = "HTTPS",
    ) -> aws.lb.TargetGroup:
        """Add a target group for the load balancer and return it.

        If a target group already exists for the group_id, it will be returned.

        Args:
            group_id: A string identifying the group. Must be unique across
                      all of this load balancer's target groups.
            short_name: A string identifying the group. Must be unique across
                        all of this load balancer's target groups. This is used
                        in resource naming and must be <= 4 characters.
            ttype: The target type for the group. One of `ip`, `instance`, or
                   `lambda`. Defaults to `instance`
            healthcheck_args: An optional dict of health check args. If not
                               provided, the health check will default to a
                               ping on the traffic port.
            port: The port for the target group. Defaults to 443
            proto: The protocol for the target group. Defaults to HTTPS

        Returns:
            The new target group if created or the existing one for the
            group_id.
        """
        # make sure we were given a valid target type
        if ttype not in ("ip", "instance", "lambda"):
            raise ValueError(
                f"Target group type {ttype} is invalid for ALB {self.name}."
            )

        # NOTE: these all seem sensible defaults for now. The one exception is a
        #       lambda target group, which we give a longer interval. the lambda
        #       interval must be longer than the runtime of the lambda, so this
        #       value is not guaranteed to work for all lambda targets and if
        #       not, the healthcheck_args arg for this method needs to be
        #       overridden.
        default_hc_args = {
            "path": "/ping",
            "port": "traffic-port",
            "protocol": "HTTPS",
            "matcher": "200",
            "interval": 45 if ttype == "lambda" else 30,
        }

        if group_id in self._target_groups:
            return self._target_groups[group_id]

        hc_args = (
            healthcheck_args
            if healthcheck_args is not None
            else default_hc_args
        )

        tghc_args = aws.lb.TargetGroupHealthCheckArgs(**hc_args)

        self._target_groups[group_id] = aws.lb.TargetGroup(
            f"{self.name}-tg-{short_name}",
            port=port,
            protocol=proto,
            protocol_version="HTTP1",
            target_type=ttype,
            vpc_id=self._vpc_id,
            health_check=tghc_args,
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} ALB {group_id} {ttype} " f"target group"
                ),
            },
        )

        return self._target_groups[group_id]

    def _add_target_group_attachments(
        self,
        target_name: str,
        target_group: aws.lb.TargetGroup,
        targets: list[tuple[str, str]],
        port: int | None = None,
    ):
        """Attach a list of targets to a target group.

        Args:
            target_group:
            targets: A list of target values (tuples of strings) for the group
                     attachment. What the values of the first element of the
                     tuple is depends on the `target_type` of the target group:
                        * When the type is `ip`, the first element should be
                          the ip addresses of network interfaces.
                        * When type is `instance` the first element should be
                          the ec2 instance or ECS container id.
                        * When the type is `lambda`, the first element should be
                          the arns of lambda function.
                    In all cases, the second element of the tuple should be the
                    availbaility zone identifier
            port: Optional port to use in the attachment. This should only be
                  specified for non-lambda targets
        """
        for tval, az in targets:
            aws.lb.TargetGroupAttachment(
                # TODO: do not love having the target value (e.g. ip address)
                #       in the resource name here. seems that it's not ok to
                #       use outputs in resource names (except perhaps if they
                #       are made stack references?), so can't use target_group
                #       name and type as desired...
                f"{target_name}-{tval}-{az}-atch",
                target_group_arn=target_group.arn,
                target_id=tval,
                port=port,
                opts=ResourceOptions(parent=self, depends_on=[target_group]),
            )

    def _get_listener(self, port, proto):
        """Return the requested listener or raise a standard exception.

        Args:
            port: The port the listener is on.
            proto: The protocol the listener is listening for.

        Returns:
            The configured listener for the port/proto combination.

        Raises:
            KeyError: If there is no configured listener for the port/proto
                      combination
        """
        listener = self._listeners.get((port, proto), None)
        if listener is None:
            raise KeyError(
                f"Not ALB listener has been configured for port:proto {port}:"
                f"{proto}. A listener must be configured with add_listener "
                f"before targets can be added."
            )
        return listener

    def _get_nic_attr_tuple(
        self, nir: aws.ec2.AwaitableGetNetworkInterfaceResult
    ) -> tuple[str, str]:
        """Get an attribute tuple for a network interface get result.

        The tuple contains the private ip address and availability zone for the
        NIC.

        Args:
            nir: The GetNetworkInterfacesResult to get the tuple for.
        """
        return (nir.private_ip, nir.availability_zone)

    def add_listener(
        self,
        port: int,
        proto: str,
        acmcert: aws.acm.Certificate | None = None,
    ):
        """Create a listener for the ALB on the given port/proto and return it.

        NOTE: Listeners must be added before calling `add_XXX_target` methods

        If a listener already exists for the given port/proto combination, it
        will be returned.

        Args:
            port: The port the listener will listen on.
            proto: The protocol the listener is listening for.
            acmcert: The ACM cert to associate with the listener.
        """
        # NOTE: As there can only be one listener per port/proto combo and the
        #       listener holds the cert, there can be only one cert associated
        #       with each combo

        if (port, proto) in self._listeners:
            return self._listeners[(port, proto)]

        # TODO: ISSUE #133
        self._listeners[(port, proto)] = aws.lb.Listener(
            f"{self.name}-{proto}-{port}-lstnr",
            load_balancer_arn=self.alb.arn,
            certificate_arn=acmcert.arn if acmcert else None,
            port=port,
            protocol=proto,
            default_actions=[
                aws.lb.ListenerDefaultActionArgs(
                    type="fixed-response",
                    fixed_response=(
                        aws.lb.ListenerDefaultActionFixedResponseArgs(
                            content_type="text/html",
                            message_body=FIXED_403,
                            status_code="403",
                        )
                    ),
                ),
            ],
            tags={
                "desc_name": (f"{self.desc_name} ALB {port}:{proto} Listener"),
            },
            opts=ResourceOptions(parent=self),
        )

        return self._listeners[(port, proto)]

    def add_static_app_target(
        self,
        bucket: aws.s3.BucketV2,
        vpc_ep: aws.ec2.VpcEndpoint,
        sa_name: str,
        sa_short_name: str,
        port: int | None = 443,
        proto: str | None = "HTTPS",
    ):
        """Set an S3 hosted static app as a target for the ALB.

        This method adds a target group, target group attachments, a listener,
        and listener rules for the static app. The listener will forward all
        requests to the provided VPC endpoint

        NOTE: The only redirect rule set up for the static app is to append
              `index.html` to any path ending in a slash. Everything else is
              allowed through to the S3 vpc endpoint and will be served if it
              exists. Be sure there are no secrets in the static app deployed.

        Args:
            vpc_ep: The VPC endpoint to associate with this static app.
            sa_name: The unique name of the static app being setup with this
                     ALB.
            sa_short_name: The unique short name of the static app being setup
                           with this ALB. This is used in resource naming and
                           must be <= 4 characters.
            port: The port the of the listener the app will be associated with.
                  Defaults to 443
            proto: The protocol of the listener the app will be associated with.
                   Defaults to HTTPS
        """

        listener = self._get_listener(port, proto)

        # All static sites will be routed to IP target groups.

        # NOTE: at this time all target group healtch checks for static apps
        #       will be checking for a HTTP GET on port 80 returning a 200, 307
        #       or 405. This is probably sufficient for a general health check
        #       of s3 static sites, but may need to be tweaked for some stuff
        #       down the line
        sa_tg = self._add_target_group(
            f"{sa_name}",
            f"{sa_short_name}",
            ttype="ip",
            healthcheck_args={
                "path": "/",
                "port": "80",
                "protocol": "HTTP",
                "matcher": "200,307,405",
            },
        )

        # the vpc endpoint for s3 has a list of network interfaces. we need to
        # associate the ip addrs of those interfaces with new target group
        # attachments for the target group so we can forward traffic there. as
        # the list of interfaces is a list of Outputs, need to apply on it to
        # get the value and use that to get the ip string to pass on the that
        # attachment helper.
        vpc_ep.network_interface_ids.apply(
            lambda l: self._add_target_group_attachments(
                sa_short_name,
                sa_tg,
                [
                    self._get_nic_attr_tuple(get_network_interface(id=i))
                    for i in l
                ],
            )
        )

        # This is the only redirect rule setup for the static app. If the path
        # ends in a slash, we append `index.html` and then re-evaluate.
        conditions_action_desc = [
            ("*/", "/#{path}index.html", "Rule for trailing slash."),
        ]

        # TODO: ISSUE #133
        # NOTE: this is in a loop even though there is only one
        #       condition/action pair currently. Originally there were more
        #       rules, and leaving it this way allows us to easily add more if
        #       needed.
        for idx, (ptrn, redir, desc) in enumerate(
            conditions_action_desc, start=1
        ):
            aws.lb.ListenerRule(
                f"{self.name}-{sa_short_name}-lstnrrl{idx}",
                listener_arn=listener.arn,
                conditions=[
                    # for static apps, we want to match the host header (bucket
                    # name is fqdn of the app) *and* the path pattern. this
                    # keeps us from conflicting with other hosts on the same alb
                    # and mucking with their paths
                    aws.lb.ListenerRuleConditionArgs(
                        host_header=aws.lb.ListenerRuleConditionHostHeaderArgs(
                            values=[bucket.bucket.apply(lambda n: f"{n}")],
                        ),
                    ),
                    aws.lb.ListenerRuleConditionArgs(
                        path_pattern=aws.lb.ListenerRuleConditionPathPatternArgs(
                            values=[ptrn],
                        ),
                    ),
                ],
                actions=[
                    aws.lb.ListenerRuleActionArgs(
                        type="redirect",
                        redirect=aws.lb.ListenerRuleActionRedirectArgs(
                            path=redir,
                            protocol="HTTPS",
                            # Permanent redirect for caching
                            status_code="HTTP_301",
                        ),
                    ),
                ],
                priority=self.next_rule_priority,
                opts=ResourceOptions(parent=self),
                tags={
                    "desc_name": (
                        f"{self.desc_name} {sa_name} ALB 443 HTTPS Listener "
                        f"{desc}"
                    ),
                },
            )

        # Add a rule to forward all items that don't match above to the target
        # group for this application.
        # NOTE: This rule must be under all others (at a higher priority value)
        # so that all other rules apply first te get redirects correct.
        fwd_rule_idx = len(conditions_action_desc) + 1
        aws.lb.ListenerRule(
            f"{self.name}-{sa_short_name}-lstnrrl{fwd_rule_idx}",
            listener_arn=listener.arn,
            conditions=[
                aws.lb.ListenerRuleConditionArgs(
                    host_header=aws.lb.ListenerRuleConditionHostHeaderArgs(
                        values=[bucket.bucket.apply(lambda n: f"{n}")],
                    ),
                ),
                aws.lb.ListenerRuleConditionArgs(
                    path_pattern=aws.lb.ListenerRuleConditionPathPatternArgs(
                        values=[f"/*"],
                    ),
                ),
            ],
            actions=[
                aws.lb.ListenerRuleActionArgs(
                    type="forward",
                    forward=aws.lb.ListenerRuleActionForwardArgs(
                        target_groups=[
                            aws.lb.ListenerRuleActionForwardTargetGroupArgs(
                                arn=sa_tg.arn,
                                weight=1,
                            )
                        ],
                    ),
                ),
            ],
            priority=self.next_rule_priority,
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} {sa_name} ALB 443 HTTPS Listener "
                    f"Rule for forward to {sa_name} target group"
                ),
            },
        )

    # TODO: a lot of shared boilerplate here with static app stuff
    def add_instance_app_target(
        self,
        instance: aws.ec2.Instance,
        app_name: str,
        app_short_name: str,
        fqdn: str,
        port: int | None = 443,
        proto: str | None = "HTTPS",
        fwd_port: int | None = 80,
        fwd_proto: str | None = "HTTP",
        hc_args: dict | None = None,
    ):
        """Set an EC2 instance hosted app as a target for the ALB.

        This method adds a target group, target group attachments, a listener,
        and listener rules for the EC2 instance. The listener will forward all
        requests to the provided instance.

        NOTE: The protocol and port to use for forwarding to the instance can
              be configured, but by default it is assumed that the load
              balancer will handle TLS termination if needed and communications
              with the instance will happen over 80/HTTP. In order to use
              443/HTTPS from the ALB to the instance, certs will need to be set
              up and that *is not* handled here.

        Args:
            instance: The EC2 instance hosting the application.
            app_name: The unique name of the application being setup with this
                      ALB.
            app_short_name: The unique short name of the application being
                            setup with this ALB. This is used in resource
                            naming and must be <= 4 characters.
            fqdn: The FQDN for requests that should be routed to the instance.
            port: The port the of the listener the app will be associated with.
                  Defaults to 443
            proto: The protocol of the listener the app will be associated
                   with. Defaults to HTTPS
            fwd_port: The port to forward to on the instance. Defaults to 80.
            fwd_proto: The protocol to use in forwarding to the instance.
                       Defaults to HTTP.
            hc_args: A dict of healtch check args to be passed directly to the
                     target group for the instance. These will be passed
                     *as-is* to the target group. This is useful if the app on
                     the instance does not return an HTTP 200 from the default
                     endpoint used by AWS. (e.g. if `curl http://[instance_ip]`
                     returns something like 302 FOUND, or if HTTPS is required,
                     etc)
        """

        listener = self._get_listener(port, proto)

        # NOTE: if not specified otherwise, all target group health checks for
        #       instances will be checking for the default health checks
        hca = (
            hc_args
            if hc_args is not None
            else {
                "path": "/",
                "port": "80",
                "protocol": "HTTP",
            }
        )

        app_tg = self._add_target_group(
            f"{app_name}",
            f"{app_short_name}",
            ttype="instance",
            healthcheck_args=hca,
            # Port is specified for the target group even though the value
            # will also be specified in the target group attachment below,
            # which will override if the ports are in conflict. Seems target
            # group port becomes important with autoscaling groups, which we may
            # or may not need at some point...
            port=fwd_port,
            proto=fwd_proto,
        )

        # for instance targets, the list we pass the attachment helper needs
        # should contain string ids of the instances we're attaching to
        Output.all(i=instance.id, a=instance.availability_zone).apply(
            lambda args: self._add_target_group_attachments(
                app_short_name,
                app_tg,
                [(f"{args['i']}", f"{args['a']}")],
                port=fwd_port,
            )
        )

        # For instance targets, we will forward anything with the correct host
        # header to the instance.
        aws.lb.ListenerRule(
            f"{self.name}-{app_short_name}-lstnrrl",
            listener_arn=listener.arn,
            conditions=[
                aws.lb.ListenerRuleConditionArgs(
                    host_header=aws.lb.ListenerRuleConditionHostHeaderArgs(
                        values=[f"{fqdn}"],
                    ),
                ),
            ],
            actions=[
                aws.lb.ListenerRuleActionArgs(
                    type="forward",
                    forward=aws.lb.ListenerRuleActionForwardArgs(
                        target_groups=[
                            aws.lb.ListenerRuleActionForwardTargetGroupArgs(
                                arn=app_tg.arn,
                                weight=1,
                            )
                        ],
                    ),
                ),
            ],
            priority=self.next_rule_priority,
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} {app_name} ALB 443 HTTPS Listener "
                    f"Rule for forward to {app_name} target group"
                ),
            },
        )

    # TODO: a lot of shared boilerplate here with static app stuff
    def add_api_target(
        self,
        vpc_ep: aws.ec2.VpcEndpoint,
        api_stage_name: str,
        api_short_name: str,
        port: int | None = 443,
        proto: str | None = "HTTPS",
    ):
        """Set an API gateway behind a VPC endpoint as a target for the ALB.

        This method adds a target group, target group attachments, a listener
        (if not added already), and listener rules for the api. The listener
        will forward all requests to the provided VPC endpoint


        Args:
            vpc_ep: The VPC endpoint to associate with this static app.
            api_stage_name: The unique name of the api being setup with this
                            ALB. This will be the path after the alb hostname
                            that will be used to route to the stage identified
                            by api_stage_id. The API path after the alb
                            hostname must match the name of the deployed stage
                            in API gateway.
            api_short_name: The unique short name of the api being setup with
                            this ALB. This will be used in resource naming and
                            must be >= 4 characters.
            port: The port the of the listener the app will be associated with.
                  Defaults to 443
            proto: The protocol of the listener the app will be associated with.
                   Defaults to HTTPS
        """

        listener = self._get_listener(port, proto)

        # All APIs will be routed to IP target groups
        api_tg = self._add_target_group(
            f"{api_stage_name}", f"{api_short_name}", ttype="ip"
        )

        # the vpc endpoint for the api gateway has a list of network
        # interfaces. we need to associate the ip addrs of those interfaces
        # with new target group attachments for the target group so we can
        # forward traffic there. as the list of interfaces is a list of
        # Outputs, need to apply on it to get the value and use that to get the
        # ip string to pass on the that attachment helper.

        vpc_ep.network_interface_ids.apply(
            lambda l: self._add_target_group_attachments(
                api_short_name,
                api_tg,
                [
                    self._get_nic_attr_tuple(get_network_interface(id=i))
                    for i in l
                ],
            )
        )

        # add the rule for forwarding a seemingly well formatted api request.
        # TODO: at this time we do not handle rewrite of request paths to remove
        #       trailing slashes. this would be nice, but certainly not a
        #       non-starter since the apis are private
        aws.lb.ListenerRule(
            f"{self.name}-{api_short_name}-lstnrrl",
            listener_arn=listener.arn,
            conditions=[
                aws.lb.ListenerRuleConditionArgs(
                    path_pattern=aws.lb.ListenerRuleConditionPathPatternArgs(
                        values=[f"/{api_stage_name}/*"],
                    ),
                ),
            ],
            actions=[
                aws.lb.ListenerRuleActionArgs(
                    type="forward",
                    forward=aws.lb.ListenerRuleActionForwardArgs(
                        target_groups=[
                            aws.lb.ListenerRuleActionForwardTargetGroupArgs(
                                arn=api_tg.arn,
                                weight=1,
                            )
                        ],
                    ),
                ),
            ],
            priority=self.next_rule_priority,
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} {api_stage_name} ALB 443 HTTPS "
                    f"Listener Rule for forward to {api_stage_name} target "
                    "group"
                ),
            },
        )
