"""Focused tests for the dormant EFS-backed Batch capability."""

import ast
import base64
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]


def _load_bootstrap_renderer():
    source = (REPO_ROOT / "capeinfra/pipeline/batch.py").read_text()
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "render_host_bootstrap_user_data"
    )
    module = ast.fix_missing_locations(
        ast.Module(body=[function], type_ignores=[])
    )
    namespace = {"base64": base64, "json": json}
    exec(compile(module, "batch.py", "exec"), namespace)
    return namespace["render_host_bootstrap_user_data"]


def test_render_host_bootstrap_user_data_writes_efs_contract():
    render_host_bootstrap_user_data = _load_bootstrap_renderer()
    mounts = [
        {
            "name": "reference-data",
            "fileSystemId": "fs-0123456789abcdef0",
            "mountPath": "/mnt/reference_data",
            "readOnly": True,
            "tls": True,
            "iam": True,
        }
    ]

    encoded = render_host_bootstrap_user_data(
        {"efs_mounts": {"required": True, "mounts": mounts}}
    )
    script = base64.b64decode(encoded).decode()
    mounts_json = json.dumps(
        {"version": 1, "mounts": mounts},
        separators=(",", ":"),
        sort_keys=True,
    )

    assert script.startswith("MIME-Version: 1.0")
    assert (
        'Content-Type: multipart/mixed; boundary="==CAPE_EFS_BOOTSTRAP=="'
        in script
    )
    assert "Content-Type: text/cloud-boothook" in script
    assert base64.b64encode(mounts_json.encode()).decode() in script
    assert "ECS_EFS_MOUNTER_REQUIRED=true" in script
    assert "/etc/ecs/efs-mounts.json.tmp" in script
    assert "/etc/ecs/efs-mounter.env.tmp" in script
    assert "systemctl restart ecs-efs-mounter.service" not in script


def test_render_host_bootstrap_defaults_mounter_to_required():
    render_host_bootstrap_user_data = _load_bootstrap_renderer()
    encoded = render_host_bootstrap_user_data(
        {
            "efs_mounts": {
                "mounts": [
                    {
                        "name": "reference-data",
                        "fileSystemId": "fs-0123456789abcdef0",
                        "mountPath": "/mnt/reference_data",
                        "readOnly": True,
                        "tls": True,
                        "iam": True,
                    }
                ]
            }
        }
    )

    assert "ECS_EFS_MOUNTER_REQUIRED=true" in base64.b64decode(encoded).decode()


@pytest.mark.parametrize(
    "host_bootstrap",
    [
        {},
        {"efs_mounts": {}},
        {"efs_mounts": {"mounts": []}},
        {"efs_mounts": {"required": "yes", "mounts": [{}]}},
    ],
)
def test_render_host_bootstrap_rejects_invalid_efs_configuration(
    host_bootstrap,
):
    render_host_bootstrap_user_data = _load_bootstrap_renderer()

    with pytest.raises(ValueError):
        render_host_bootstrap_user_data(host_bootstrap)


def test_efs_capability_documentation_covers_child_mount_contract():
    documentation = (REPO_ROOT / "extra-doc/README.efs-batch.md").read_text()

    assert "host_bootstrap" in documentation
    assert "security_group_source" in documentation
    assert "/etc/ecs/efs-mounts.json" in documentation
    assert "/etc/ecs/efs-mounter.env" in documentation
    assert (
        "volumes = '/mnt/reference_data:/mnt/reference_data:ro'"
        in documentation
    )
    assert "path` input" in documentation
