# Shared pipeline assets

CAPE stores shared, immutable pipeline assets in the meta-assets S3 bucket. The
bucket is created by CAPE infrastructure, but large asset payloads are not
managed as Pulumi `FileAsset` objects.

## Manifest layout

Keep one small JSON manifest per asset version under:

```text
assets/pipeline-assets/manifests/
```

The manifest records the upstream source, publication version, checksums,
expected sizes, consumers, and immutable publish prefix. The current Standard-8
manifest is:

```text
assets/pipeline-assets/manifests/kraken2-bracken-standard-8-2026-06-26.json
```

Its runtime S3 directory is:

```text
pipelines/shared/databases/kraken2-bracken/standard-8/2026-06-26/database/
```

Asset versions are immutable. A new upstream release adds a new manifest and a
new prefix; it never replaces an existing prefix.

## Planning a publication

The portable Python planner validates all manifests and produces a deterministic
aggregate plan. It has no Pulumi dependency and does not download or upload a
payload yet:

```bash
python -m pipeline_assets.publisher \
    --manifest-dir assets/pipeline-assets/manifests \
    --bucket <meta-assets-bucket>
```

Limit the plan to one asset with `--asset-id`:

```bash
python -m pipeline_assets.publisher \
    --asset-id kraken2-bracken-standard-8 \
    --bucket <meta-assets-bucket>
```

The eventual publisher will use the same manifest contract to download into
temporary scratch, validate the upstream checksum and database contents, upload
the immutable `database/` directory, and write its generated manifest last.
The archive and expanded database must not be kept in the repository.

## Pulumi and deployment ownership

Pulumi owns the shared bucket, IAM, lifecycle rules, and the stack output that
identifies the bucket. Pulumi should not perform the large download. A manual
command, CI job, or the future `cape-cod-env` deployment can invoke the
portable publisher after the infrastructure exists.

The publisher target should come from the Pulumi environment handoff rather
than a physical bucket name in a pipeline fixture. The asset manifest remains
portable when publication moves from `cape-cod` to `cape-cod-env`.

## Reproducibility

Runtime references should use an explicit asset ID and version. Do not use a
mutable `latest` path for an analysis run. Record the selected manifest and
content digest with the run metadata. Retain old asset versions while analyses
or reports reference them.
