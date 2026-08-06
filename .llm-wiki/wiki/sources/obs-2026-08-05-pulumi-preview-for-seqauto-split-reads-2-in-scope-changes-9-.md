---
type: source
title: "Observation: pulumi preview for seqauto split-reads: 2 in-scope changes + 9 pre-existing drift/build churn, no destructive ops"
slug: obs-2026-08-05-pulumi-preview-for-seqauto-split-reads-2-in-scope-changes-9-
status: observation
created: 2026-08-05
updated: 2026-08-05
relevance: high
observed_at: 2026-08-05T14:29:33.943Z
tags: ["pulumi", "preview", "seqauto", "etl", "phase1", "drift", "deploy"]
source_context: "Phase 1 pre-deploy pulumi preview evaluation"
---
# ⭐ Observation: pulumi preview for seqauto split-reads: 2 in-scope changes + 9 pre-existing drift/build churn, no destructive ops
Ran `pulumi preview --diff -s cape-cod-dev` for the seqauto split-reads branch (361-...). Result: 10 to update, 1 to replace, 460 unchanged. Token was live; preview took a few minutes (rebuilt report-gen lambda layer + resolved deps).

The 2 changes attributable to THIS branch, both correct and non-destructive:
- `aws:s3/bucketObjectv2` `glue/etl/etl_seqarchive.py` - script asset hash 0c445c3 -> 80cacf6 (the split-reads ETL edit; Glue job needs no change, it references the object).
- `aws:glue/crawler:Crawler` `ccd-dlh-T-seqauto-input-clean-vbkt-crwl-gcrwl` - exclusions add `[1]: "sequencing-reads-split/**"` next to existing `sequencing-reads/**`.

The other 9 are pre-existing drift / build-nondeterminism churn, NOT from this branch:
- report-gen lambda layer rebuild (4): `report-gen/manifest.txt` + `report-gen/layer.zip` asset hashes change -> forces `report-gen` LayerVersion REPLACE (the single +-1) -> `getcannedreport` function layers[1] -> [unknown]. Caused by pip re-resolving weasyprint/jinja deps into a new layer hash at preview time.
- nextflow image rebuild (3): `docker-build:index:Image` contextHash -> [unknown], cascading to `nextflow-jobdef` Batch job definition + its `nextflow-jobdef-pssrl-plcy` IAM policy.
- `aws:cognito/identityProvider` GTRI-SSO providerDetails drops SSO cert + redirect URIs (real SSO-side drift).
- `aws:cognito/user` demo@example.com temporaryPassword [secret]=>[secret] (perpetual secret diff).

Safety: no shared stateful resources (buckets/DBs/queues) deleted or replaced; the only replace is an immutable Lambda layer version (safe). Caveat for deploy: a `pulumi up` would also apply the 9 unrelated changes - with two devs on the infra, confirm the report-gen/nextflow churn and cognito drift are expected (not a colleague's in-flight work) before the user deploys. See [[concepts/testing-and-pulumi-preview-workflow]].
*Relevance: high*

*Context: Phase 1 pre-deploy pulumi preview evaluation*

*Tags: pulumi preview seqauto etl phase1 drift deploy*
---
*Observed: 2026-08-05T14:29:33.943Z*