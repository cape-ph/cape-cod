"""Tests for the portable pipeline asset manifest planner."""

import json
from pathlib import Path

import pytest

from pipeline_assets import (
    AssetManifestError,
    build_publish_plan,
    load_manifests,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "assets/pipeline-assets/manifests"


def test_standard_8_manifest_contains_upstream_provenance():
    manifests = load_manifests(MANIFEST_DIR)
    assert len(manifests) == 1

    manifest = manifests[0]
    assert manifest.asset_id == "kraken2-bracken-standard-8"
    assert manifest.version == "2026-06-26"
    assert manifest.data["collection"] == "Standard-8"
    assert manifest.data["source"]["archiveSizeGb"] == 5.5
    assert manifest.data["source"]["indexSizeGb"] == 7.5


def test_build_publish_plan_resolves_bucket_and_database_path():
    plan = build_publish_plan(
        load_manifests(MANIFEST_DIR), "s3://cape-meta-assets"
    )

    assert plan["schemaVersion"] == 1
    assert plan["bucket"] == "cape-meta-assets"
    assert plan["assets"][0]["databasePath"] == (
        "s3://cape-meta-assets/"
        "pipelines/shared/databases/kraken2-bracken/standard-8/2026-06-26/"
        "database/"
    )


def test_build_publish_plan_rejects_duplicate_asset_versions(tmp_path):
    source = json.loads(
        (
            MANIFEST_DIR / "kraken2-bracken-standard-8-2026-06-26.json"
        ).read_text()
    )
    for name in ("one.json", "two.json"):
        (tmp_path / name).write_text(json.dumps(source))

    with pytest.raises(AssetManifestError, match="Duplicate asset manifest"):
        build_publish_plan(load_manifests(tmp_path), "cape-meta-assets")


def test_manifest_rejects_parent_path_prefix(tmp_path):
    source = json.loads(
        (
            MANIFEST_DIR / "kraken2-bracken-standard-8-2026-06-26.json"
        ).read_text()
    )
    source["publish"]["rootPrefix"] = "pipelines/../outside"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(source))

    with pytest.raises(AssetManifestError, match="relative S3 prefix"):
        load_manifests(tmp_path)
