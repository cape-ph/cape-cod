# Lambda request authorizer for the CAPE API.
#
# Responsibilities:
# - Decide allow/deny for the caller (currently allow-all; real policy TBD).
# - Resolve the caller's identity from the Cognito bearer token and pass it
#   downstream to endpoint handlers via the authorizer `context`. Handlers read
#   this identity (e.g. to stamp the triggering user onto an Airflow DAG run)
#   instead of trusting client-supplied values.
#
# TODO (authz hardening, tracked for follow-up):
# - This does NOT verify the JWT signature yet. It decodes the token payload for
#   identity only. Before production, either verify the signature against the
#   Cognito JWKS here, or replace this lambda authorizer with a managed Cognito
#   (JWT) authorizer on the API. Until then, treat the resolved identity as
#   authenticated-by-transport-only, not cryptographically verified.
# - Move to real allow/deny decisions once identity is trustworthy.

import base64
import binascii
import json


def lambda_handler(event, context):
    """API Gateway request authorizer entrypoint.

    Returns an IAM policy plus a `context` map carrying the caller identity
    (as strings, per API Gateway's authorizer-context constraints).
    """
    headers = event.get("headers") or {}
    identity = identity_context_from_headers(headers)

    # principalId should be a stable identifier for the caller when we have one.
    principal_id = identity.get("triggering_user_id") or "unknown"

    return generate_policy(principal_id, "Allow", "*", context=identity)


def get_bearer_token(headers):
    """Extract a bearer token from request headers (case-insensitive).

    :param headers: The request headers mapping (may be None).
    :return: The raw token string, or None if not present.
    """
    if not headers:
        return None

    # API Gateway header casing is not guaranteed; match case-insensitively.
    auth_value = None
    for key, value in headers.items():
        if key.lower() == "authorization":
            auth_value = value
            break

    if not auth_value:
        return None

    parts = auth_value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()

    # Allow a bare token with no scheme prefix as a fallback.
    return auth_value.strip() or None


def decode_jwt_claims(token):
    """Decode the (unverified) claim set from a JWT.

    NOTE: This does not validate the signature. See module TODO.

    :param token: A JWT string (header.payload.signature).
    :return: A dict of claims, or {} if the token can't be parsed.
    """
    if not token or not isinstance(token, str):
        return {}

    segments = token.split(".")
    if len(segments) < 2:
        return {}

    payload_segment = segments[1]
    # JWT uses base64url without padding; restore padding before decoding.
    padding = "=" * (-len(payload_segment) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_segment + padding)
        claims = json.loads(decoded)
    except (ValueError, binascii.Error, json.JSONDecodeError):
        return {}

    return claims if isinstance(claims, dict) else {}


def identity_context_from_claims(claims):
    """Build the downstream authorizer context from Cognito claims.

    :param claims: The decoded JWT claims dict.
    :return: A dict with `triggering_user_id` and `triggering_user_name` keys for
             any values we could resolve. Missing values are omitted so callers
             can distinguish "unknown".
    """
    context = {}

    # `sub` is the stable Cognito user id; prefer it for the filterable id.
    user_id = claims.get("sub")
    if user_id:
        context["triggering_user_id"] = str(user_id)

    # Human-readable name for admin/UI display: email, then cognito username.
    user_name = (
        claims.get("email")
        or claims.get("cognito:username")
        or claims.get("username")
    )
    if user_name:
        context["triggering_user_name"] = str(user_name)

    return context


def identity_context_from_headers(headers):
    """Resolve caller identity context directly from request headers.

    Convenience wrapper composing token extraction and claim decoding.
    """
    token = get_bearer_token(headers)
    claims = decode_jwt_claims(token)
    return identity_context_from_claims(claims)


def generate_policy(principal_id, effect, resource, context=None):
    """Build an API Gateway authorizer response.

    :param principal_id: Identifier for the caller.
    :param effect: "Allow" or "Deny".
    :param resource: The resource ARN(s) the policy applies to.
    :param context: Optional string-valued map passed to downstream handlers.
    """
    authz_resp = {"principalId": principal_id}

    if effect and resource:
        authz_resp["policyDocument"] = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        }

    # API Gateway only supports string/number/bool context values (no nesting).
    authz_resp["context"] = context or {}

    return authz_resp
