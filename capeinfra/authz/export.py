"""Builds the ABAC resource catalog export for the deployed infrastructure.

This module produces a JSON-serializable snapshot of the resources CAPE deploys,
shaped for the `cape-cod-db` authorization schema (a `Tributary` + `Resource`
catalog). It intentionally emits plain dicts and does NOT depend on the
`cape_cod_db` package: the export writes nothing and holds no access logic, so
the ORM/migration stack stays out of the IaC environment. `cape-cod-env`
validates the export against the models when it syncs the database.

Scope for v1 is the datalake tributary S3 buckets. Access is not encoded here:
`Resource` is a pure catalog and `attributes.category` is the stable descriptor
that policy (OPA/Rego) maps to a default action downstream. Per-user/per-subject
grants live in `cape-cod-db`'s `ResourceGrant` table, populated elsewhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pulumi import Output, log

if TYPE_CHECKING:
    from capeinfra.datalake.datalake import DatalakeHouse

# Export envelope version. Bump when the JSON shape changes in a way consumers
# must react to.
EXPORT_VERSION = "1.0"

# Canonical resource_type for S3 resources (matches cape-cod-db fixtures).
RESOURCE_TYPE_S3 = "s3"

# Provenance marker so the cape-cod-env reconcile can scope what it manages.
MANAGED_BY = "cape-cod-pulumi"

# Category assigned to tributary buckets whose id does not match the standard
# [input|result]-[raw|clean] scheme. Policy grants nothing for it by default.
UNKNOWN_CATEGORY = "other"

# Datalake bucket id (prefix, suffix) -> cape-cod-db attributes.category. Policy
# maps raw -> write and clean -> read; that derivation lives in Rego, not here.
CATEGORY_BY_BUCKET_ID: dict[tuple[str, str], str] = {
    ("input", "raw"): "raw_uploads",
    ("input", "clean"): "clean_uploads",
    ("result", "raw"): "raw_results",
    ("result", "clean"): "clean_results",
}


def _category_for_bucket_id(bucket_id: str) -> str:
    """Map a tributary bucket id to its cape-cod-db resource category.

    Args:
        bucket_id: The tributary bucket id, e.g. ``input-raw``.

    Returns:
        The category string, or ``UNKNOWN_CATEGORY`` for non-standard ids.
    """
    parts = bucket_id.split("-")
    if len(parts) != 2:
        return UNKNOWN_CATEGORY
    return CATEGORY_BY_BUCKET_ID.get((parts[0], parts[1]), UNKNOWN_CATEGORY)


def _display_label(category: str) -> str:
    """Return a human-readable label for a category (e.g. ``raw_uploads`` ->
    ``Raw Uploads``)."""
    return category.replace("_", " ").title()


def _resource_record(
    *,
    bucket_name: str,
    bucket_arn: str,
    bucket_id: str,
    tributary_code: str,
    tributary_display_name: str,
    stack: str,
) -> dict[str, Any]:
    """Build a single S3 ``Resource`` catalog record.

    The record maps to a cape-cod-db ``Resource`` row: ``resource_type``,
    ``resource_identifier`` (the real ``s3://`` path AWS assigned),
    ``display_name``, and JSONB ``attributes``. It carries no access value;
    ``attributes.category`` is the descriptor policy uses to derive access.
    ``tributary_code`` and ``bucket_role`` are duplicated into ``attributes`` so
    the cape-cod-env reconcile can key on logical identity even if the physical
    bucket name (and thus ``resource_identifier``) changes on replacement.

    Args:
        bucket_name: The AWS-assigned physical bucket name.
        bucket_arn: The bucket ARN.
        bucket_id: The tributary bucket id (e.g. ``input-raw``).
        tributary_code: The owning tributary's short code.
        tributary_display_name: The owning tributary's human-readable name.
        stack: The Pulumi stack name (recorded as the environment).

    Returns:
        A JSON-serializable resource record dict.
    """
    category = _category_for_bucket_id(bucket_id)
    return {
        "resource_type": RESOURCE_TYPE_S3,
        "resource_identifier": f"s3://{bucket_name}/",
        "display_name": f"{tributary_display_name} {_display_label(category)}",
        "attributes": {
            "bucket": bucket_name,
            "arn": bucket_arn,
            "category": category,
            "bucket_role": bucket_id,
            "tributary_code": tributary_code,
            "environment": stack,
            "managed_by": MANAGED_BY,
        },
    }


def _assemble_export(
    resolved_buckets: list[dict[str, str]],
    bucket_meta: list[tuple[str, str, str]],
    tributaries: list[dict[str, Any]],
    stack: str,
) -> dict[str, Any]:
    """Assemble the export envelope from resolved bucket values (pure).

    Args:
        resolved_buckets: Per-bucket ``{"name", "arn"}`` dicts, aligned to
            ``bucket_meta`` by index.
        bucket_meta: Per-bucket ``(tributary_code, tributary_display_name,
            bucket_id)`` tuples.
        tributaries: Ordered tributary dicts (``code``, ``name``,
            ``description``); resources are attached to these by code.
        stack: The Pulumi stack name.

    Returns:
        The full export dict.
    """
    by_code: dict[str, dict[str, Any]] = {
        t["code"]: {**t, "resources": []} for t in tributaries
    }
    for resolved, (code, display_name, bucket_id) in zip(
        resolved_buckets, bucket_meta
    ):
        by_code[code]["resources"].append(
            _resource_record(
                bucket_name=resolved["name"],
                bucket_arn=resolved["arn"],
                bucket_id=bucket_id,
                tributary_code=code,
                tributary_display_name=display_name,
                stack=stack,
            )
        )
    return {
        "version": EXPORT_VERSION,
        "pulumi_stack": stack,
        "tributaries": list(by_code.values()),
    }


def _collect_export_inputs(
    dlh: "DatalakeHouse",
) -> tuple[
    list[dict[str, Any]], list[tuple[str, str, str]], list[Output[dict]]
]:
    """Walk a datalake house and gather the export inputs (no resolution).

    Separated from ``build_resource_export`` so the tributary/bucket iteration
    is unit-testable without a Pulumi runtime: the bucket name/ARN Outputs are
    collected but not resolved here.

    Args:
        dlh: The DatalakeHouse whose tributaries/buckets are exported.

    Returns:
        A tuple of (ordered tributary dicts, per-bucket
        ``(tributary_code, tributary_display_name, bucket_id)`` metadata,
        per-bucket ``{"name", "arn"}`` Outputs), aligned by index for the
        latter two.
    """
    tributaries: list[dict[str, Any]] = []
    bucket_meta: list[tuple[str, str, str]] = []
    bucket_outputs: list[Output[dict]] = []

    for trib in dlh.tributaries:
        tributaries.append(
            {
                "code": trib.code,
                "name": trib.display_name,
                "description": trib.description,
            }
        )
        for bucket_id, vbkt in trib.buckets.items():
            bucket_meta.append((trib.code, trib.display_name, bucket_id))
            bucket_outputs.append(
                Output.all(name=vbkt.bucket.bucket, arn=vbkt.bucket.arn)
            )

    return tributaries, bucket_meta, bucket_outputs


def build_resource_export(dlh: "DatalakeHouse", stack: str) -> Output[dict]:
    """Build the ABAC resource catalog export for a datalake house.

    Walks the configured tributaries and their buckets, resolving the real
    AWS-assigned bucket name and ARN Outputs, and returns an Output of the
    JSON-serializable export envelope suitable for ``pulumi.export``.

    Args:
        dlh: The DatalakeHouse whose tributaries/buckets are exported.
        stack: The Pulumi stack name (recorded as the environment).

    Returns:
        A pulumi Output resolving to the export dict.
    """
    tributaries, bucket_meta, bucket_outputs = _collect_export_inputs(dlh)

    for code, _display_name, bucket_id in bucket_meta:
        if _category_for_bucket_id(bucket_id) == UNKNOWN_CATEGORY:
            log.warn(
                f"tributary {code} bucket id '{bucket_id}' is not a standard "
                f"[input|result]-[raw|clean] bucket; exporting with category "
                f"'{UNKNOWN_CATEGORY}'."
            )

    return Output.all(*bucket_outputs).apply(
        lambda resolved: _assemble_export(
            resolved, bucket_meta, tributaries, stack
        )
    )
