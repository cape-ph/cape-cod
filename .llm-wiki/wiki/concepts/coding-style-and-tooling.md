---
type: concept
title: "Coding Style and Tooling Policy"
slug: coding-style-and-tooling
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["tooling", "formatting", "style", "pi-lens", "pyright", "black"]
---

# Coding Style and Tooling Policy

This page is the authoritative record of the formatters, linters, and language
servers configured for CAPE Cod. The intent is that any agent (pi-lens included)
matches the existing tooling exactly and does not introduce new tools.

## Formatters (authoritative)

- Python: black (line length 80) + isort (`profile = "black"`, line length 80).
  Enforced by pre-commit (`black 24.8.0`, `isort 5.13.2`) and by the VSCode
  Python extensions (`ms-python.black-formatter`, `ms-python.isort`) with
  format-on-save and `source.organizeImports` on save.
- YAML / JSON / Markdown: Prettier (`esbenp.prettier-vscode`), configured by
  `.prettierrc.yaml` (`proseWrap: always`, `tabWidth: 4`, `useTabs: false`;
  Markdown uses the markdown parser). Note the `.editorconfig` sets
  `max_line_length = 0` for `*.{yaml,yml,md,j2}`, so wrapping there is governed
  by Prettier, not a hard column.
- TOML: editor support only via `tamasfe.even-better-toml` (no reformatter in
  pre-commit).

## Linters / type checking

- Type checking: Pyright in `basic` mode (`pyrightconfig.json`),
  `autoImportCompletions: true`, ignoring `assets/etl/**`. This is the language
  server of record for Python.
- flake8 is explicitly disabled for all Python files (`.vscode/settings.json`:
  `"flake8.ignorePatterns": ["**/*.py"]`).
- ruff appears in `pyproject.toml` only as `[tool.ruff] line-length = 80`. It is
  NOT run by pre-commit or CI and is not a configured formatter/linter. Do not
  run `ruff format` or `ruff check` as part of normal edits.
- typos (crate-ci/typos) runs in pre-commit with `.typos.toml` exclusions
  (`assets/web/*`, and allowed words `ser`, `ue`, `ot`, `attch`).

## pi-lens policy for this repo

- Format Python with black + isort at line length 80. Never reformat Python with
  ruff-format, biome, or any other formatter.
- Format YAML/JSON/Markdown with Prettier settings above.
- Use Pyright (basic) for diagnostics; do not add mypy/flake8/ruff diagnostics.
- Do not introduce biome, eslint, mypy, or new language servers/formatters. The
  `.opencode/` directory (an OpenCode plugin sandbox with `node_modules`) is
  tooling scaffolding, not a JS/TS project - do not treat it as one.

## Style conventions observed in the code

- Line length 80 everywhere (black, isort, ruff, `.editorconfig`
  `max_line_length = 80` for code).
- 4-space indentation.
- Extensive docstrings: module docstrings, and Google-style Args/Returns/Raises
  on most methods. Match this when adding functions.
- Comments carry reasoning and TODOs (often with `ISSUE #NNN` references);
  preserve that intent rather than deleting.
- Every construct subclasses `CapeComponentResource` and defines `type_name`
  (and `default_config`/`policies` where relevant). See
  [[concepts/capepulumi-base-classes]].
- Python target is 3.10 (`.tool-versions`, `.mise.toml`). A comment in
  `capepulumi.py` notes string-enum improvements are deferred until 3.11+, so do
  not assume 3.11+ features.

## Local environment

- `.tool-versions` / `.mise.toml`: python 3.10, pulumi 3, pre-commit 3.
- The `venv/` used by Pulumi contains runtime deps and `pytest` but NOT black,
  isort, or pyright - those are provided by pre-commit's isolated environments
  and the editor extensions. Running `black`/`isort` directly requires
  installing them or using `pre-commit run`.

Related: [[syntheses/cape-cod-architecture-overview]],
[[concepts/testing-and-pulumi-preview-workflow]].
