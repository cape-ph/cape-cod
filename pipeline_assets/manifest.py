"""Load and validate portable pipeline asset manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AssetManifestError(ValueError):
    """Raised when a pipeline asset manifest is invalid."""


@dataclass(frozen=True)
class AssetManifest:
    """A validated, repository-defined pipeline asset manifest."""

    path: Path
    data: dict[str, Any]

    @property
    def asset_id(self) -> str:
        return self.data["assetId"]

    @property
    def version(self) -> str:
        return self.data["version"]

    @property
    def identity(self) -> tuple[str, str]:
        return self.asset_id, self.version

    @property
    def root_prefix(self) -> str:
        return self.data["publish"]["rootPrefix"].rstrip("/")

    @property
    def database_prefix(self) -> str:
        return f"{self.root_prefix}/database/"

    def publish_plan(self, bucket: str) -> dict[str, Any]:
        """Return the resolved S3 destinations without performing a publish."""
        bucket = bucket.removeprefix("s3://").rstrip("/")
        return {
            "assetId": self.asset_id,
            "version": self.version,
            "manifestPath": str(self.path),
            "s3Root": f"s3://{bucket}/{self.root_prefix}/",
            "databasePath": f"s3://{bucket}/{self.database_prefix}",
            "source": self.data["source"],
            "consumers": self.data.get("consumers", []),
        }


def _require_string(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AssetManifestError(f"{context}.{key} must be a non-empty string")
    return value


def load_manifest(path: Path) -> AssetManifest:
    """Load and validate one JSON manifest."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise AssetManifestError(f"Invalid JSON in {path}: {error}") from error

    if not isinstance(data, dict):
        raise AssetManifestError(f"Manifest {path} must contain an object")

    context = str(path)
    if data.get("schemaVersion") != 1:
        raise AssetManifestError(f"{context}.schemaVersion must be 1")
    _require_string(data, "assetId", context)
    _require_string(data, "assetKind", context)
    _require_string(data, "version", context)

    source = data.get("source")
    if not isinstance(source, dict):
        raise AssetManifestError(f"{context}.source must be an object")
    _require_string(source, "archiveUrl", f"{context}.source")
    _require_string(source, "md5Url", f"{context}.source")

    publish = data.get("publish")
    if not isinstance(publish, dict):
        raise AssetManifestError(f"{context}.publish must be an object")
    root_prefix = _require_string(publish, "rootPrefix", f"{context}.publish")
    if root_prefix.startswith("/") or ".." in Path(root_prefix).parts:
        raise AssetManifestError(
            f"{context}.publish.rootPrefix must be a relative S3 prefix"
        )

    consumers = data.get("consumers", [])
    if not isinstance(consumers, list) or any(
        not isinstance(consumer, str) or not consumer.strip()
        for consumer in consumers
    ):
        raise AssetManifestError(f"{context}.consumers must be a string list")

    return AssetManifest(path=path, data=data)


def load_manifests(manifest_dir: Path) -> list[AssetManifest]:
    """Load all JSON manifests below a directory in stable order."""
    paths = sorted(manifest_dir.glob("**/*.json"))
    if not paths:
        raise AssetManifestError(
            f"No JSON manifests found under {manifest_dir}"
        )
    return [load_manifest(path) for path in paths]


def build_publish_plan(
    manifests: list[AssetManifest], bucket: str
) -> dict[str, Any]:
    """Build one aggregate publish plan from per-asset manifests."""
    seen: set[tuple[str, str]] = set()
    prefixes: set[str] = set()
    assets = []
    for manifest in manifests:
        if manifest.identity in seen:
            raise AssetManifestError(
                f"Duplicate asset manifest identity: {manifest.asset_id}@{manifest.version}"
            )
        if manifest.root_prefix in prefixes:
            raise AssetManifestError(
                f"Duplicate asset publish prefix: {manifest.root_prefix}"
            )
        seen.add(manifest.identity)
        prefixes.add(manifest.root_prefix)
        assets.append(manifest.publish_plan(bucket))

    return {
        "schemaVersion": 1,
        "bucket": bucket.removeprefix("s3://").rstrip("/"),
        "assets": assets,
    }
