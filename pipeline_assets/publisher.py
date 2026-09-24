"""Plan and publish immutable pipeline assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.request import Request, urlopen

import boto3

from .manifest import AssetManifest, build_publish_plan, load_manifests

_MD5_LINE = re.compile(r"^(?P<digest>[0-9a-fA-F]{32})\s+[*]?(?P<name>.+?)\s*$")


def _new_md5():
    """Create MD5 for compatibility with upstream checksum metadata only."""
    return hashlib.new("md5", usedforsecurity=False)


def _download(url: str, destination: Path) -> tuple[str, str, int]:
    """Download a source archive and return MD5, SHA256, and byte count."""
    md5 = _new_md5()
    sha256 = hashlib.sha256()
    size = 0
    request = Request(url, headers={"User-Agent": "cape-pipeline-assets/1"})
    with urlopen(request) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            md5.update(chunk)
            sha256.update(chunk)
            size += len(chunk)
    return md5.hexdigest(), sha256.hexdigest(), size


def _read_md5_file(url: str) -> dict[str, str]:
    """Read the upstream checksum list keyed by basename."""
    request = Request(url, headers={"User-Agent": "cape-pipeline-assets/1"})
    text = urlopen(request).read().decode("utf-8")
    checksums = {}
    for line in text.splitlines():
        match = _MD5_LINE.match(line.strip())
        if match:
            checksums[Path(match.group("name")).name] = match.group(
                "digest"
            ).lower()
    if not checksums:
        raise ValueError(f"No MD5 entries found at {url}")
    return checksums


def _normalized_member_name(
    member_name: str, strip_root: str | None
) -> str | None:
    """Normalize one safe archive member path for the database directory."""
    path = PurePosixPath(member_name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe archive member path: {member_name}")
    parts = path.parts
    if strip_root and parts and parts[0] == strip_root:
        parts = parts[1:]
    if not parts:
        return None
    return PurePosixPath(*parts).as_posix()


def _extract_database(
    archive: Path, destination: Path, checksums: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """Extract, checksum, and return metadata for database files."""
    with tarfile.open(archive, mode="r:gz") as tar:
        members = tar.getmembers()
        roots = {
            PurePosixPath(member.name).parts[0]
            for member in members
            if PurePosixPath(member.name).parts
        }
        strip_root = roots.pop() if len(roots) == 1 else None
        if roots:
            strip_root = None

        file_metadata = {}
        for member in members:
            relative_name = _normalized_member_name(member.name, strip_root)
            if relative_name is None or member.isdir():
                continue
            if not member.isfile():
                raise ValueError(
                    f"Unsupported archive member type: {member.name}"
                )

            output_path = destination / relative_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            md5 = _new_md5()
            sha256 = hashlib.sha256()
            source = tar.extractfile(member)
            if source is None:
                raise ValueError(
                    f"Unable to read archive member: {member.name}"
                )
            with source, output_path.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    md5.update(chunk)
                    sha256.update(chunk)

            actual_md5 = md5.hexdigest()
            expected_md5 = checksums.get(Path(relative_name).name)
            if expected_md5 is None:
                raise ValueError(f"No upstream MD5 entry for {relative_name}")
            if actual_md5 != expected_md5:
                raise ValueError(
                    f"MD5 mismatch for {relative_name}: "
                    f"expected {expected_md5}, got {actual_md5}"
                )
            file_metadata[relative_name] = {
                "sizeBytes": output_path.stat().st_size,
                "md5": actual_md5,
                "sha256": sha256.hexdigest(),
            }

    expected_files = {name for name in checksums if name != archive.name}
    actual_files = {Path(name).name for name in file_metadata}
    if expected_files != actual_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        raise ValueError(
            f"Database file inventory mismatch; missing={missing}, extra={extra}"
        )
    return file_metadata


# TODO(#386): Split format-specific publication adapters from this CLI when a
# second asset publication format makes the boundary concrete.
def publish_asset(
    manifest: AssetManifest,
    bucket: str,
    scratch_dir: Path | None = None,
) -> dict[str, Any]:
    """Download, validate, and publish one immutable asset version."""
    bucket = bucket.removeprefix("s3://").rstrip("/")
    s3 = boto3.client("s3")
    prefix = manifest.root_prefix.rstrip("/")
    existing = s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefix}/", MaxKeys=1)
    if existing.get("KeyCount", 0):
        raise ValueError(
            f"Asset publish prefix already exists: s3://{bucket}/{prefix}/"
        )

    source = manifest.data["source"]
    with tempfile.TemporaryDirectory(dir=scratch_dir) as temporary:
        temp_root = Path(temporary)
        archive = temp_root / Path(source["archiveUrl"]).name
        archive_md5, archive_sha256, archive_size = _download(
            source["archiveUrl"], archive
        )
        checksums = _read_md5_file(source["md5Url"])
        expected_archive_md5 = checksums.get(archive.name)
        if expected_archive_md5 and archive_md5 != expected_archive_md5:
            raise ValueError(
                f"Archive MD5 mismatch: expected {expected_archive_md5}, got {archive_md5}"
            )

        database = temp_root / "database"
        file_metadata = _extract_database(archive, database, checksums)
        for relative_name in sorted(file_metadata):
            s3.upload_file(
                str(database / relative_name),
                bucket,
                f"{prefix}/database/{relative_name}",
                ExtraArgs={"ServerSideEncryption": "AES256"},
            )

        generated_manifest = {
            "schemaVersion": 1,
            **manifest.data,
            "published": {
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "archiveSizeBytes": archive_size,
                "archiveMd5": archive_md5,
                "archiveSha256": archive_sha256,
                "objectCount": len(file_metadata),
                "sizeBytes": sum(
                    item["sizeBytes"] for item in file_metadata.values()
                ),
                "files": file_metadata,
            },
        }
        s3.put_object(
            Bucket=bucket,
            Key=f"{prefix}/manifest.json",
            Body=json.dumps(
                generated_manifest, indent=2, sort_keys=True
            ).encode(),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )

    return {
        "assetId": manifest.asset_id,
        "version": manifest.version,
        "databasePath": f"s3://{bucket}/{prefix}/database/",
        "manifestPath": f"s3://{bucket}/{prefix}/manifest.json",
        "objectCount": len(file_metadata),
        "sizeBytes": sum(item["sizeBytes"] for item in file_metadata.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or publish immutable pipeline assets."
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path("assets/pipeline-assets/manifests"),
        help="Directory containing per-asset JSON manifests.",
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="S3 bucket name or s3:// URI for the shared meta-assets bucket.",
    )
    parser.add_argument(
        "--asset-id", help="Limit the operation to one asset ID."
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Download, validate, and publish one asset instead of printing a plan.",
    )
    parser.add_argument(
        "--scratch-dir",
        type=Path,
        help="Parent directory for temporary download and extraction scratch.",
    )
    args = parser.parse_args()

    manifests = load_manifests(args.manifest_dir)
    if args.asset_id:
        manifests = [
            manifest
            for manifest in manifests
            if manifest.asset_id == args.asset_id
        ]
        if not manifests:
            parser.error(f"No manifest found for asset ID {args.asset_id}")

    if args.publish:
        if len(manifests) != 1:
            parser.error(
                "--publish requires exactly one manifest or --asset-id"
            )
        print(
            json.dumps(
                publish_asset(manifests[0], args.bucket, args.scratch_dir),
                indent=2,
            )
        )
    else:
        print(
            json.dumps(
                build_publish_plan(manifests, args.bucket),
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
