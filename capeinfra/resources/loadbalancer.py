"""Module of load balancer related resources."""

import pulumi_aws as aws
from pulumi import Input, Output, ResourceOptions, warn
from pulumi_aws.ec2.get_network_interface import get_network_interface

from capeinfra.resources.pulumi import CapeComponentResource

# TODO:In order for this ALB implementation to support more than just a single
#      static app (e.g. if we want multiple APIs or apps - static or not) we
#      will require nothing to be served from the root of the ALB, but rather
#      have paths that we can differentiate with. e.g. if the alb is linked
#      with the fqdn myalb.tld we need things like myalb.tld/api1 or
#      myalb.tld/app2. we want the default action of listeners to return a
#      fixed response (e.g. a 403) if we don't have some sort of landing page
#      (if we have a landing page then the default action can just forward to
#      the target group for the landing page assuming that target group is
#      known at the time the listener is created) and then add listener rules
#      that match the paths to then forward to the right target group. Another
#      option is to only support one item per load balancer (or support
#      multiple with paths for things like APIs and just one for apps). The
#      cost of an ALB at the time of this writing is $0.0225/hr.


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

    def _add_target_group(
        self,
        group_id: str,
        ttype: str = "instance",
        healthcheck_args: dict | None = None,
    ) -> aws.lb.TargetGroup:
        """Add a target group for the load balancer and return it.

        If a target group already exists for the group_id, it will be returned.

        Args:
            group_id: A string identifying the group. Must be unique across
                      all of this load balancer's target groups.
            ttype: The target type for the group. One of `ip`, `instance`, or
                   `lambda`. Defaults to `instance`
            healthchaeck_args: An optional dict of health check args. If not
                               provided, the health check will default to a
                               ping on the traffic port.

        Returns:
            The new target group if created or the existing one for the
            group_id.
        """
        # make sure we were given a valid target type
        if ttype not in ("ip", "instance", "lambda"):
            raise ValueError(
                f"Target group type {ttype} is invalid for ALB {self.name}."
            )

        # NOTE: at this time we only support HTTPS or 443 for target groups
        tg_port = 443
        tg_proto = "HTTPS"
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

        # TODO: ISSUE #167 - putting a count in the resource name instead of
        #                    group_id due to naming length limits
        tg_idx = len(self._target_groups)
        self._target_groups[group_id] = aws.lb.TargetGroup(
            f"{self.name}-tg-{tg_idx}",
            port=tg_port,
            protocol=tg_proto,
            protocol_version="HTTP1",
            target_type=ttype,
            vpc_id=self._vpc_id,
            health_check=tghc_args,
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} ALB {group_id} {ttype} target group"
                ),
            },
        )

        return self._target_groups[group_id]

    def _add_target_group_attachments(
        self, target_group: aws.lb.TargetGroup, targets: list[str]
    ):
        """Attach a list of targets to a target group.

        Args:
            target_group:
            targets: A list of target values (strings) for the group
                     attachment. What the values are is determined by the
                     `target_type` of the target group:
                        * When the type is `ip`, the  list should contain ip
                          addresses of network interfaces.
                        * When type is `instance` the list should contain ec2
                          instance or ECS container ids.
                        * When the type is `lambda`, the list should contain
                          arns of lambda functions.
        """
        for idx, tval in enumerate(targets):
            aws.lb.TargetGroupAttachment(
                # TODO: do not love having the target value (e.g. ip address)
                #       in the resource name here. seems that it's not ok to
                #       use outputs in resource names (except perhaps if they
                #       are made stack references?), so can't use target_group
                #       name and type as desired...
                f"{tval}-atch{idx}",
                target_group_arn=target_group.arn,
                target_id=tval,
                port=443,
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
        vpc_ep: aws.ec2.VpcEndpoint,
        sa_name: str,
        sa_paths: set,
        port: int | None = 443,
        proto: str | None = "HTTPS",
    ):
        """Set an S3 hosted static app as a target for the ALB.

        This method adds a target group, target group attachments, a listener,
        and listener rules for the static app. The listener will forward all
        requests to the provided VPC endpoint

        NOTE: It is assumed that all provided paths for rules should ultimately
              end in serving an `index.html` file from the path and that the
              app exists in a prefix that is the same as the `sa_name` value
              given.

        Args:
            vpc_ep: The VPC endpoint to associate with this static app.
            sa_name: The unique name of the static app being setup with this
                     ALB.
            sa_paths: A set of paths (no leading slash) that will be allowed for
                      this target.
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
                sa_tg, [get_network_interface(id=i).private_ip for i in l]
            )
        )

        # the following code up some rules around rewriting request paths
        # where the url ends in a trailing slash or a an application (path)
        # name. as all of our apps are served as a single `index.html`
        # file in the static app case, we need to rewrite the url to
        # actually be for that file. this is because the default behavior
        # of s3 is to provide a file listing when given a url ending in a
        # trailing slash. that would be no bueno

        # first build the list of patterns (for conditions) and
        # rewrites/redirects (for actions). we will always have a default
        # that handles paths ending in trailing slashes or just the static app
        # name
        conditions_actions = [
            (f"/{sa_name}*/", "/#{path}index.html"),
            (f"/{sa_name}", "/#{path}/index.html"),
        ]

        # this constant action will work for all of our conditions and so we
        # only need to define it once
        actn = "/#{path}/index.html"

        # NOTE: sa_paths is a set. Sets are not ordered. So if we do not sort
        #       in some way, we will probably get a different order every time
        #       we iterate over it when we make listener rules. This means that
        #       the index-based listener rules will probably appear different
        #       to pulumi every deployment. This is an attempt to mitigate that
        #       somewhat.
        #       The downside to this (being sorted alphbetically) is that if
        #       we add a new path that fits somewhere in the middle of the
        #       sorted list, all listeners after that entry would appear to
        #       be changed on that deployment...
        for pth in sorted(sa_paths):
            # we can ignore "." path here as that is the root of the s3
            # bucket and would be covered by the default case.
            if pth != ".":
                # pth will look like `a/b/c` relative to the root of the s3
                # bucket. the condition for that will look like `/a/b/c` and
                # the action will be the constant defined above
                conditions_actions.append((f"/{sa_name}/{pth}", actn))

        # TODO: ISSUE #133
        # priorities for these rules are executed lowest to highest (and range
        # on 1-50000). so have the list here in the order you want them tried
        # in and the idx will take care of the priority
        for idx, (ptrn, redir) in enumerate(conditions_actions, start=1):
            aws.lb.ListenerRule(
                f"{self.name}-{sa_name}-lstnrrl{idx}",
                listener_arn=listener.arn,
                conditions=[
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
                priority=idx,
                opts=ResourceOptions(parent=self),
                tags={
                    "desc_name": (
                        f"{self.desc_name} {sa_name} ALB 443 HTTPS Listener "
                        # TODO: can't have * in a tag value. would be nice to
                        #       use some text here that's more useful than
                        #       PATTERN WITH A STAR
                        f"Rule for "
                        f"{'PATTERN WITH A STAR' if '*' in ptrn else ptrn}"
                    ),
                },
            )

        # Add a rule to forward all items that don't match above to the target
        # group for this application.
        # NOTE: This rule must be under all others (at a higher priority value)
        # so that all other rules apply first te get redirects correct.
        # TODO: This may not a good idea. It allows direct access to everything
        #       in the hierarchy for the static app (which may be ok, may not).
        #       SEE THE TODO AT THE TOP OF THIS FILE
        aws.lb.ListenerRule(
            f"{self.name}-{sa_name}-lstnrrl{len(conditions_actions)+1}",
            listener_arn=listener.arn,
            conditions=[
                aws.lb.ListenerRuleConditionArgs(
                    path_pattern=aws.lb.ListenerRuleConditionPathPatternArgs(
                        values=[f"/{sa_name}/*"],
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
            priority=len(conditions_actions) + 1,
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} {sa_name} ALB 443 HTTPS Listener "
                    f"Rule for forward to {sa_name} target group"
                ),
            },
        )

    # TODO: a lot of shared boilerplate here with static app stuff
    def add_api_target(
        self,
        vpc_ep: aws.ec2.VpcEndpoint,
        api_stage_name: str,
        # TODO: remove stage id
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
            port: The port the of the listener the app will be associated with.
                  Defaults to 443
            proto: The protocol of the listener the app will be associated with.
                   Defaults to HTTPS
        """

        listener = self._get_listener(port, proto)

        # All APIs will be routed to IP target groups
        api_tg = self._add_target_group(f"{api_stage_name}", ttype="ip")

        # the vpc endpoint for the api gateway has a list of network
        # interfaces. we need to associate the ip addrs of those interfaces
        # with new target group attachments for the target group so we can
        # forward traffic there. as the list of interfaces is a list of
        # Outputs, need to apply on it to get the value and use that to get the
        # ip string to pass on the that attachment helper.

        vpc_ep.network_interface_ids.apply(
            lambda l: self._add_target_group_attachments(
                api_tg, [get_network_interface(id=i).private_ip for i in l]
            )
        )

        # add the rule for forwarding a seemingly well formatted api request.
        # TODO: at this time we do not handle rewrite of request paths to remove
        #       trailing slashes. this would be nice, but certainly not a
        #       non-starter since the apis are private
        aws.lb.ListenerRule(
            f"{self.name}-{api_stage_name}-lstnrrl1",
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
            priority=1,
            opts=ResourceOptions(parent=self),
            tags={
                "desc_name": (
                    f"{self.desc_name} {api_stage_name} ALB 443 HTTPS "
                    f"Listener Rule for forward to {api_stage_name} target "
                    "group"
                ),
            },
        )
