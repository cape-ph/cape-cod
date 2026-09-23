"""Generate small runtime database sheets from immutable asset references."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from .manifest import AssetManifest


def build_database_sheet(
    manifest: AssetManifest, runtime_export: dict[str, Any]
) -> str:
    """Build a taxprofiler-compatible sheet from an asset and runtime export."""
    sheet_config = manifest.data.get("runtime", {}).get("databaseSheet")
    if not isinstance(sheet_config, dict):
        raise ValueError(
            f"Asset {manifest.asset_id}@{manifest.version} has no database sheet configuration"
        )

    assets = runtime_export.get("pipelineAssets")
    if not isinstance(assets, dict) or not assets.get("bucket"):
        raise ValueError("Runtime export has no pipelineAssets.bucket")

    bucket = str(assets["bucket"]).removeprefix("s3://").rstrip("/")
    rows = [
        [
            sheet_config["tool"],
            sheet_config["dbName"],
            sheet_config.get("dbParams", ""),
            sheet_config.get("dbType", ""),
            f"s3://{bucket}/{manifest.database_prefix}",
        ]
    ]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["tool", "db_name", "db_params", "db_type", "db_path"])
    writer.writerows(rows)
    return output.getvalue()


def write_database_sheet(
    manifest: AssetManifest,
    runtime_export_path: Path,
    output_path: Path,
) -> None:
    """Write one generated database sheet from a runtime export JSON file."""
    try:
        runtime_export = json.loads(runtime_export_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Unable to read runtime export {runtime_export_path}: {error}"
        ) from error
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_database_sheet(manifest, runtime_export))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a database sheet from an asset manifest and runtime export."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runtime-export", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from .manifest import load_manifest

    write_database_sheet(
        load_manifest(args.manifest), args.runtime_export, args.output
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
