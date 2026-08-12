---
type: source
title: "Observation: pi-lens prettier reindents 2-space Pulumi.cape-cod-public.yaml; .prettierignore fix"
tags:
  - tooling
  - prettier
  - pi-lens
  - formatting
  - pulumi-config
status: observation
created: 2026-08-12
updated: 2026-08-12
slug: obs-2026-08-12-pi-lens-prettier-reindents-2-space-pulumi-cape-cod-public-ya
relevance: high
observed_at: 2026-08-12T21:28:24.055Z
source_context: Wiring report/get endpoint in CAPI
---

# ⭐ Observation: pi-lens prettier reindents 2-space Pulumi.cape-cod-public.yaml; .prettierignore fix

pi-lens auto-formats edited files with prettier after every turn using the repo's .prettierrc.yaml (tabWidth: 4). Pulumi.cape-cod-public.yaml is committed at 2-space indentation, so pi-lens kept reindenting the entire file to 4-space each turn (1789/1761 line churn) - a large out-of-scope diff. The repo's pre-commit does NOT run prettier (only trailing-whitespace, mixed-line-ending, check-yaml/toml, check-merge-conflict, black, isort, typos), so that reindent is not an enforced repo change. Fix: added .prettierignore with `Pulumi.*.yaml` so prettier/pi-lens skip the hand-maintained stack config files; this kept the public change to a minimal +16 diff. NOTE: the .prettierignore is a new repo-wide file that needs maintainer approval. Also: HEAD's capi-openapi-301.yaml.j2 already carries 59 lines of pre-existing trailing whitespace; the pre-commit trailing-whitespace hook will strip them at commit time (unrelated to the report/get change). Edits to the 2-space public yaml must be done via a byte-preserving script (python rb/wb split on "\n"), not the edit tool, to avoid triggering the whole-file reindent.

*Relevance: high*
*Context: Wiring report/get endpoint in CAPI*
*Tags: tooling prettier pi-lens formatting pulumi-config*

---
*Observed: 2026-08-12T21:28:24.055Z*
