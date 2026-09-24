"""Tests for the portable pipeline asset manifest planner."""

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from pipeline_assets import (
    AssetManifestError,
    build_publish_plan,
    load_manifests,
)
from pipeline_assets import publisher as asset_publisher
from pipeline_assets.database_sheet import build_database_sheet

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "assets/pipeline-assets/manifests"


def _write_archive(path, members):
    with tarfile.open(path, mode="w:gz") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


def _md5(content):
    digest = hashlib.new("md5", usedforsecurity=False)
    digest.update(content)
    return digest.hexdigest()


def _standard_manifest():
    return load_manifests(MANIFEST_DIR)[0]


class _FakeS3:
    def __init__(self, key_count=0):
        self.key_count = key_count
        self.events = []

    def list_objects_v2(self, **kwargs):
        return {"KeyCount": self.key_count}

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        self.events.append(("upload", filename, bucket, key, ExtraArgs))

    def put_object(self, **kwargs):
        self.events.append(("manifest", kwargs))


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


def test_build_database_sheet_resolves_runtime_bucket():
    manifest = load_manifests(MANIFEST_DIR)[0]
    runtime_export = {
        "pipelineAssets": {
            "bucket": "ccd-meta-assets-vbkt-s3-test",
        }
    }

    assert build_database_sheet(manifest, runtime_export) == (
        "tool,db_name,db_params,db_type,db_path\n"
        "kraken2,standard-8,,long,"
        "s3://ccd-meta-assets-vbkt-s3-test/"
        "pipelines/shared/databases/kraken2-bracken/standard-8/2026-06-26/"
        "database/\n"
    )


def test_read_md5_file_parses_bare_and_starred_names(monkeypatch):
    md5_text = (
        "0123456789abcdef0123456789abcdef  archive.tar.gz\n"
        "fedcba9876543210fedcba9876543210 *nested/database.k2d\n"
        "not a checksum line\n"
    )
    monkeypatch.setattr(
        asset_publisher,
        "urlopen",
        lambda request: io.BytesIO(md5_text.encode()),
    )

    assert asset_publisher._read_md5_file("https://example.test/checksums") == {
        "archive.tar.gz": "0123456789abcdef0123456789abcdef",
        "database.k2d": "fedcba9876543210fedcba9876543210",
    }


def test_extract_database_rejects_archive_path_traversal(tmp_path):
    archive = tmp_path / "unsafe.tar.gz"
    _write_archive(archive, {"../outside.k2d": b"unsafe"})

    with pytest.raises(ValueError, match="Unsafe archive member path"):
        asset_publisher._extract_database(
            archive,
            tmp_path / "database",
            {
                archive.name: _md5(archive.read_bytes()),
                "outside.k2d": _md5(b"unsafe"),
            },
        )
    assert not (tmp_path / "outside.k2d").exists()


def test_extract_database_rejects_checksum_mismatch(tmp_path):
    archive = tmp_path / "database.tar.gz"
    content = b"database"
    _write_archive(archive, {"kraken/hash.k2d": content})

    with pytest.raises(ValueError, match="MD5 mismatch for hash.k2d"):
        asset_publisher._extract_database(
            archive,
            tmp_path / "database",
            {"hash.k2d": "0" * 32},
        )


def test_extract_database_rejects_inventory_mismatch(tmp_path):
    archive = tmp_path / "database.tar.gz"
    content = b"database"
    _write_archive(archive, {"kraken/hash.k2d": content})

    with pytest.raises(ValueError, match="inventory mismatch"):
        asset_publisher._extract_database(
            archive,
            tmp_path / "database",
            {
                "hash.k2d": _md5(content),
                "opts.k2d": _md5(b"missing"),
            },
        )


def test_publish_asset_rejects_existing_immutable_prefix(monkeypatch):
    fake_s3 = _FakeS3(key_count=1)
    monkeypatch.setattr(asset_publisher.boto3, "client", lambda name: fake_s3)

    def unexpected_download(*args):
        raise AssertionError("existing prefixes must not download source data")

    monkeypatch.setattr(asset_publisher, "_download", unexpected_download)

    with pytest.raises(ValueError, match="already exists"):
        asset_publisher.publish_asset(
            _standard_manifest(), "s3://cape-meta-assets"
        )
    assert fake_s3.events == []


def test_publish_asset_writes_manifest_last_and_cleans_scratch(
    monkeypatch, tmp_path
):
    manifest = _standard_manifest()
    source_archive = tmp_path / "source.tar.gz"
    content = b"database"
    _write_archive(source_archive, {"kraken/hash.k2d": content})
    archive_md5 = _md5(source_archive.read_bytes())
    archive_sha256 = hashlib.sha256(source_archive.read_bytes()).hexdigest()
    archive_name = Path(manifest.data["source"]["archiveUrl"]).name
    checksums = {
        archive_name: archive_md5,
        "hash.k2d": _md5(content),
    }

    def fake_download(url, destination):
        destination.write_bytes(source_archive.read_bytes())
        return archive_md5, archive_sha256, source_archive.stat().st_size

    fake_s3 = _FakeS3()
    monkeypatch.setattr(asset_publisher, "_download", fake_download)
    monkeypatch.setattr(
        asset_publisher, "_read_md5_file", lambda url: checksums
    )
    monkeypatch.setattr(asset_publisher.boto3, "client", lambda name: fake_s3)
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    result = asset_publisher.publish_asset(
        manifest, "s3://cape-meta-assets", scratch
    )

    assert result["objectCount"] == 1
    assert [event[0] for event in fake_s3.events] == [
        "upload",
        "manifest",
    ]
    assert fake_s3.events[0][3].endswith("/database/hash.k2d")
    generated = json.loads(fake_s3.events[1][1]["Body"])
    assert generated["published"]["files"]["hash.k2d"]["md5"] == _md5(content)
    assert list(scratch.iterdir()) == []


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
