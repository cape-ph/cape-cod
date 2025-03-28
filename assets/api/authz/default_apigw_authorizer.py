# Basic lambda request authorizer for testing API gateway authz
# TODO:
# - once shown to work in basics, we should take this from test/sample status to
#   a real authz implementation
# - AWS docs suggest using request authorizers over token authorizers as the
#   former can be used for finer grained policies and caching. we should figure
#   out which better suits our needs, but for now we're following the advice.


def lambda_handler(event, context):

    # TODO: remove this debug printing
    print(f"Lambda authz event: {event}")
    print(f"Lambda authz context: {context}")

    # figure out the caller from the request
    # TODO: we can use headers, query string params, stage variables, path
    #       parameters, and context variables to figure out who's calling. need
    #       to figure out the best mix for all our services. client side (api
    #       caller) has the ability to set path params, headers and query
    #       params. all others are set by AWS

    headers = event["headers"]
    query_params = event["queryStringParameters"]
    path_params = event["pathParameters"]
    stage_vars = event["stageVariables"]

    # TODO: remove this debug printing
    print(f"Lambda authz headers: {headers}")
    print(f"Lambda authz query_params: {query_params}")
    print(f"Lambda authz path_params: {path_params}")
    print(f"Lambda authz stage_vars: {stage_vars}")

    # Parse the input for the parameter values

    # TODO:
    # - can do things like get the methodARN out of the event, use that to get
    #   the identifier of the APIGW, account number, region, restapi id, stage,
    #   method, etc as part of what to grant access to in the returned policy

    # TODO: Check the values we determine we need against some TBD criteria and
    #       return either an allow or deny policy. E.g. for this simple test,
    #       probably want to check that a username (of the caller) provided
    #       matches the name of the user we want to allow, and otherwise deny.
    #       When denying, do so by raising `Exception("Unauthorized")` (which
    #       gives a 401)

    # TODO: right now, all shall pass. if this works, need to get front ends
    #       passing in headers and such for this authorizer to use
    return generate_policy("*", "Allow", "*")


# Shamelessly taken from the example in teh AWS docs for Lambda Authorizers.
# Changed to not be javascript style and to reduce redundancy...
def generate_policy(principalId, effect, resource):
    """"""
    authz_resp = {}
    authz_resp["principalId"] = principalId

    if effect and resource:
        policy_doc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        }

        authz_resp["policyDocument"] = policy_doc

    # TODO: sample context, this is garbage data ATM
    authz_resp["context"] = {
        "some_ctx_str": "some_ctx_str_val",
        "some_ctx_int": 42,
        "some_ctx_bool": True,
    }

    return authz_resp
