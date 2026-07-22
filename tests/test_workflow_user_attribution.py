"""Unit tests for per-user workflow-run attribution.

These cover the pure, side-effect-free helpers in the capi Lambda handlers and
the API authorizer:

- the authorizer resolving a Cognito identity from a bearer token,
- the trigger handler stamping that identity onto the DAG run ``conf`` (and
  refusing client-supplied identity), and
- the "my runs" handler resolving the caller and filtering runs by owner.

The handlers are single-file Lambdas (not importable as a package), so they are
loaded from their source paths.
"""

import base64
import importlib.util
import json
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module(name, relpath):
    path = os.path.join(REPO_ROOT, relpath)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def authorizer():
    return _load_module(
        "default_apigw_authorizer",
        "assets/api/authz/default_apigw_authorizer.py",
    )


@pytest.fixture(scope="module")
def post_workflow_run():
    return _load_module(
        "post_workflow_run",
        "assets/api/capi/handlers/post_workflow_run.py",
    )


@pytest.fixture(scope="module")
def get_workflow_runs():
    return _load_module(
        "get_workflow_runs",
        "assets/api/capi/handlers/get_workflow_runs.py",
    )


def _make_jwt(claims):
    """Build an (unsigned) JWT with the given claims payload."""

    def b64(obj):
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{b64({'alg': 'none'})}.{b64(claims)}.signature"


# ---------------------------------------------------------------------------
# Authorizer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers,expected",
    [
        ({"Authorization": "Bearer abc.def.ghi"}, "abc.def.ghi"),
        ({"authorization": "bearer abc.def.ghi"}, "abc.def.ghi"),
        ({"Authorization": "abc.def.ghi"}, "abc.def.ghi"),
        ({}, None),
        (None, None),
        ({"Authorization": ""}, None),
    ],
)
def test_get_bearer_token(authorizer, headers, expected):
    assert authorizer.get_bearer_token(headers) == expected


def test_decode_jwt_claims_valid(authorizer):
    token = _make_jwt({"sub": "user-123", "email": "a@b.org"})
    claims = authorizer.decode_jwt_claims(token)
    assert claims["sub"] == "user-123"
    assert claims["email"] == "a@b.org"


@pytest.mark.parametrize(
    "token",
    ["", None, "not-a-jwt", "only.two", 123],
)
def test_decode_jwt_claims_invalid(authorizer, token):
    assert authorizer.decode_jwt_claims(token) == {}


def test_identity_context_prefers_sub_and_email(authorizer):
    ctx = authorizer.identity_context_from_claims(
        {"sub": "user-123", "email": "a@b.org", "cognito:username": "abc"}
    )
    assert ctx == {
        "triggering_user_id": "user-123",
        "triggering_user_name": "a@b.org",
    }


def test_identity_context_falls_back_to_username(authorizer):
    ctx = authorizer.identity_context_from_claims(
        {"sub": "user-123", "cognito:username": "abc"}
    )
    assert ctx == {
        "triggering_user_id": "user-123",
        "triggering_user_name": "abc",
    }


def test_identity_context_empty_when_no_claims(authorizer):
    assert authorizer.identity_context_from_claims({}) == {}


def test_identity_context_from_headers_end_to_end(authorizer):
    token = _make_jwt({"sub": "u1", "email": "u1@x.org"})
    ctx = authorizer.identity_context_from_headers(
        {"Authorization": f"Bearer {token}"}
    )
    assert ctx == {
        "triggering_user_id": "u1",
        "triggering_user_name": "u1@x.org",
    }


def test_handler_puts_identity_in_policy_context(authorizer):
    token = _make_jwt({"sub": "u1", "email": "u1@x.org"})
    resp = authorizer.lambda_handler(
        {"headers": {"Authorization": f"Bearer {token}"}}, None
    )
    assert resp["principalId"] == "u1"
    assert resp["context"]["triggering_user_id"] == "u1"
    assert resp["context"]["triggering_user_name"] == "u1@x.org"
    assert resp["policyDocument"]["Statement"][0]["Effect"] == "Allow"


def test_handler_allows_anonymous_with_empty_context(authorizer):
    resp = authorizer.lambda_handler({"headers": {}}, None)
    assert resp["principalId"] == "unknown"
    assert resp["context"] == {}
    assert resp["policyDocument"]["Statement"][0]["Effect"] == "Allow"


# ---------------------------------------------------------------------------
# Trigger handler: conf.cape stamping
# ---------------------------------------------------------------------------


def test_caller_identity_from_event(post_workflow_run):
    event = {
        "requestContext": {
            "authorizer": {
                "triggering_user_id": "u1",
                "triggering_user_name": "u1@x.org",
            }
        }
    }
    assert post_workflow_run.caller_identity_from_event(event) == {
        "triggering_user_id": "u1",
        "triggering_user_name": "u1@x.org",
    }


def test_caller_identity_from_event_missing(post_workflow_run):
    assert post_workflow_run.caller_identity_from_event({}) == {}


def test_apply_cape_identity_sets_block(post_workflow_run):
    conf = {"pipelineConfigs": [{"pipelineId": "p1"}]}
    identity = {"triggering_user_id": "u1", "triggering_user_name": "u1@x.org"}
    result = post_workflow_run.apply_cape_identity(conf, identity)
    assert result["cape"] == identity
    # DAG params are preserved.
    assert result["pipelineConfigs"] == [{"pipelineId": "p1"}]


def test_apply_cape_identity_strips_client_supplied(post_workflow_run):
    # A caller trying to forge ownership must not succeed.
    conf = {"cape": {"triggering_user_id": "attacker"}, "pipelineConfigs": []}
    identity = {"triggering_user_id": "u1"}
    result = post_workflow_run.apply_cape_identity(conf, identity)
    assert result["cape"] == {"triggering_user_id": "u1"}


def test_apply_cape_identity_removes_forged_when_no_identity(post_workflow_run):
    conf = {"cape": {"triggering_user_id": "attacker"}, "pipelineConfigs": []}
    result = post_workflow_run.apply_cape_identity(conf, {})
    assert "cape" not in result


# ---------------------------------------------------------------------------
# List handler: caller resolution + ownership filtering
# ---------------------------------------------------------------------------


def test_caller_user_id_from_authorizer(get_workflow_runs):
    event = {"requestContext": {"authorizer": {"triggering_user_id": "u1"}}}
    assert get_workflow_runs.caller_user_id(event) == "u1"


def test_caller_user_id_qsp_fallback(get_workflow_runs):
    event = {"queryStringParameters": {"userId": "u2"}}
    assert get_workflow_runs.caller_user_id(event) == "u2"


def test_caller_user_id_none(get_workflow_runs):
    assert get_workflow_runs.caller_user_id({}) is None


@pytest.mark.parametrize(
    "run,expected",
    [
        ({"conf": {"cape": {"triggering_user_id": "u1"}}}, True),
        ({"conf": {"cape": {"triggering_user_id": "other"}}}, False),
        ({"conf": {"cape": {}}}, False),
        ({"conf": {}}, False),
        ({}, False),
        ({"conf": {"cape": "not-a-dict"}}, False),
    ],
)
def test_run_belongs_to_user(get_workflow_runs, run, expected):
    assert get_workflow_runs.run_belongs_to_user(run, "u1") is expected


def test_filter_runs_for_user(get_workflow_runs):
    runs = [
        {"dag_run_id": "a", "conf": {"cape": {"triggering_user_id": "u1"}}},
        {"dag_run_id": "b", "conf": {"cape": {"triggering_user_id": "u2"}}},
        {"dag_run_id": "c", "conf": {"cape": {"triggering_user_id": "u1"}}},
        {"dag_run_id": "d", "conf": {}},
    ]
    result = get_workflow_runs.filter_runs_for_user(runs, "u1")
    assert [r["dag_run_id"] for r in result] == ["a", "c"]


def test_filter_runs_for_user_empty(get_workflow_runs):
    assert get_workflow_runs.filter_runs_for_user(None, "u1") == []


class _FakeMwaaClient:
    """Minimal MWAA client double that serves paginated dagRuns responses."""

    def __init__(self, total, page_limit):
        self._total = total
        self._page_limit = page_limit
        self.calls = []

    def invoke_rest_api(self, **params):
        self.calls.append(params)
        offset = params["QueryParameters"]["offset"]
        page = [
            {"dag_run_id": f"run-{i}"}
            for i in range(offset, min(offset + self._page_limit, self._total))
        ]
        return {
            "RestApiResponse": {"dag_runs": page, "total_entries": self._total},
            "RestApiStatusCode": 200,
        }


def test_list_all_dag_runs_paginates(get_workflow_runs):
    total = get_workflow_runs.DAG_RUNS_PAGE_LIMIT * 2 + 5
    client = _FakeMwaaClient(total, get_workflow_runs.DAG_RUNS_PAGE_LIMIT)

    runs = get_workflow_runs._list_all_dag_runs(client, "env")

    assert len(runs) == total
    # One request per page: ceil(total / page_limit).
    assert len(client.calls) == 3
    # Every request hits the cross-DAG list endpoint via GET.
    assert all(c["Path"] == "/dags/~/dagRuns/list" for c in client.calls)
    assert all(c["Method"] == "GET" for c in client.calls)


def test_list_all_dag_runs_stops_on_empty_page(get_workflow_runs):
    client = _FakeMwaaClient(0, get_workflow_runs.DAG_RUNS_PAGE_LIMIT)

    runs = get_workflow_runs._list_all_dag_runs(client, "env")

    assert runs == []
    assert len(client.calls) == 1
