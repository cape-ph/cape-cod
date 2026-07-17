---
type: entity
title: "util modules (capeinfra/util/)"
slug: util-modules
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["util", "naming", "jinja2", "helpers"]
---

# util modules (`capeinfra/util/`)

Small stateless helper modules used across the project. All are tiny and
dependency-light.

## `naming.py`

- `disemvowel(s)` - removes vowels from each hyphen-delimited word (keeping the
  first character of each word) to shorten strings. A naive workaround for AWS
  resource name length limits. Related length pressure drives the `stack_ns`
  abbreviation in `capeinfra/__init__.py` (see
  [[syntheses/cape-cod-architecture-overview]]).

## `jinja2.py`

- `get_j2_template_from_path(tmplt_pth)` - loads a Jinja2 `Template` from a file
  path using a `FileSystemLoader` rooted at the file's parent directory.
- `get_j2_template_from_str(tmplt)` - builds a `Template` from a string.

Used to render templated assets at deploy time, e.g. the API OpenAPI spec
(`assets/api/capi/capi-openapi-301.yaml.j2`), EC2 user-data
(`assets/instance/user-data/templates/*.j2`), and analysis-pipeline fixture JSON
in `DAPRegistry.load_pipeline_assets` (which renders JSON-as-Jinja with
`aws_region`). See [[entities/dap-registry-module]] and
[[entities/cape-rest-api-module]].

## `file.py`

- `file_as_string(pth)` - reads a file to a string; raises `FileNotFoundError`
  if missing. Used e.g. by `BYOCert` to read PEM files.
- `unzip_to(zip_path, target_dir="/tmp")` - extracts a zip archive.

## `repo.py`

- `get_github_release_artifact(repo_url, artifact_name, version="latest", dl_loc="/tmp")`
  - downloads a GitHub release asset via `urllib` and returns the local path,
      or `None` if the download appears empty (checks `Content-Length`). Used by
      GitHub-release-based Lambda layers (`CapeGHReleaseLambdaLayer`). See
      [[entities/compute-module]].

Related: [[syntheses/cape-cod-architecture-overview]].
