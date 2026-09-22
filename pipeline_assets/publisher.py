"""Build and inspect a publish plan for shared pipeline assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manifest import build_publish_plan, load_manifests


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic plan for publishing pipeline assets. "
            "This command does not download or upload data."
        )
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
        "--asset-id",
        help="Limit the plan to one asset ID.",
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

    plan = build_publish_plan(manifests, args.bucket)
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
