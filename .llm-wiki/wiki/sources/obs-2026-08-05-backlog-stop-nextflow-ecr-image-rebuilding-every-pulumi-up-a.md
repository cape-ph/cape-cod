---
type: source
title:
    "Nextflow ECR image rebuilds every pulumi up: root cause, fixes, and backlog
    to stop it"
slug: obs-2026-08-05-backlog-stop-nextflow-ecr-image-rebuilding-every-pulumi-up-a
status: observation
created: 2026-08-05
updated: 2026-08-05
relevance: medium
observed_at: 2026-08-05T17:07:03.971Z
tags:
    [
        "backlog",
        "deferred",
        "pulumi",
        "awsx",
        "ecr",
        "docker-build",
        "image-rebuild",
        "devops",
        "dockerhub",
        "buildkit",
        "dns",
        "vpn",
    ]
source_context:
    "Nextflow image rebuild churn + Docker Hub base-image build timeout
    identified during the seqauto split-reads branch"
---

# Nextflow ECR image rebuilds every pulumi up: root cause, fixes, and backlog to stop it

The `nextflow_kickstart` ECR image rebuilds on almost every `pulumi up`, which
wastes deploy time and periodically breaks deploys outright. DEFERRED / BACKLOG:
do not spend current-feature time on this; pick it up on its own branch, not the
ETL/split-reads branch.

## Symptom

Intermittent `pulumi up` failure both infra devs hit, unrelated to any specific
branch:

```
docker-build:index:Image (ccd-pvsl-repo-nextflow_kickstart):
  error: failed to solve: DeadlineExceeded: amazoncorretto:21.0.8: failed to resolve source metadata for docker.io/library/amazoncorretto:21.0.8: failed to do request: Head "https://registry-1.docker.io/v2/library/amazoncorretto/manifests/21.0.8": dial tcp: lookup registry-1.docker.io: i/o timeout
Exception: resource monitor shut down
```

## Root cause

`awsx.ecr.Image` (awsx 3.1.0 / pulumi_docker_build 0.0.15) in
`capeinfra/pipeline/ecr.py` recomputes and rebuilds the image every deploy even
though its context dir (`assets/containers/nextflow-kickstart/`, just Dockerfile

- entrypoint.sh) is static and git-clean; the `docker-build:index:Image`
  contextHash flips to `[unknown]` on almost every preview (one of the known
  "superfluous" churn resources). Each rebuild bumps the `nextflow-jobdef` Batch
  revision + its IAM policy and re-resolves the base image
  `FROM amazoncorretto:21.0.8` against Docker Hub (`registry-1.docker.io`) at
  build time.

The build times out at the DNS `lookup` step -> BuildKit `DeadlineExceeded` ->
image build aborts -> Pulumi resource monitor shuts down -> the whole program
raises `resource monitor shut down`.

## Why intermittent, and the real trigger (VPN split-DNS)

BuildKit only contacts Docker Hub when the base manifest is not cached locally;
a warm cache resolves offline and succeeds. Because this image rebuilds
constantly, it re-resolves the base often, so Docker Hub anonymous per-IP pull
rate limits (worse with a shared egress IP across two devs) plus transient DNS
blips make some runs fail and others pass.

Confirmed real trigger on the affected machine: DNS resolution of
`registry-1.docker.io` failing over the VPN. Pulumi and Docker/BuildKit are Go
binaries; Go's built-in resolver reads `/etc/resolv.conf` directly (bypassing
nsswitch/systemd-resolved), and NetworkManager had written unreachable uplink
nameservers there, so every Go-resolver lookup timed out on VPN. Hopping off VPN
restored a reachable resolver and the build succeeded.

Why `docker pull amazoncorretto:21.0.8` had ZERO effect: BuildKit resolves the
`FROM` base by querying the registry for the tag's manifest digest (the "failed
to resolve source metadata" step), independent of the docker CLI's classic local
image store. The pull populated the legacy store, which BuildKit does not
consult for base resolution, so BuildKit still issued the registry HEAD through
the broken Go resolver and timed out. Misleading asymmetry: `docker pull` via
dockerd resolves through libc/nsswitch -> systemd-resolved (works on VPN), while
BuildKit's Go resolver read the broken `/etc/resolv.conf` (fails) - same box,
opposite outcomes.

## Fixes / workarounds, cheapest first

1. Re-run `pulumi up` - transient; the aborted update is partial and a clean
   re-run finishes the rest.
2. `docker login` to Docker Hub - authenticated pulls have much higher rate
   limits than anonymous per-IP.
3. Point the Docker daemon at VPN-resolvable DNS in `/etc/docker/daemon.json`
   (e.g. the VPN nameservers) so the buildkitd container inherits a working
   resolver; revert when off VPN. This stays at the daemon layer and avoids
   editing `/etc/resolv.conf`. Do NOT globally symlink `/etc/resolv.conf` to the
   systemd-resolved stub on this machine - that breaks GTRI VPN DNS.

Note: even with healthy DNS, BuildKit still does a tag->digest HEAD against the
registry each build unless the base is pinned by an already-cached digest or fed
via local OCI/build-context, so "pre-pull to go offline" does not work with
BuildKit the way it does with the legacy (`DOCKER_BUILDKIT=0`) builder. The real
win is stopping the rebuilds so routine deploys never touch any registry; the
occasional genuine rebuild is then handled by `docker login` + the daemon DNS
fix.

## Backlog: stop the rebuilds (own branch, not the ETL/split-reads branch)

1. Cheap path first: bump `pulumi_docker_build` (0.0.15 is ancient) and/or
   `pulumi-awsx`, then `pulumi preview` on an unrelated change to see if the
   image goes quiet (stable context hash). Near-zero code if it works.
2. If not: replace `awsx.ecr.Image` with `pulumi_docker_build.Image` directly
   (content-hashes the context, no-ops when unchanged); trade-off is wiring
   `registries=[...]` ECR auth (`aws.ecr.get_authorization_token`) since we lose
   awsx's push convenience.

Key correction: moving the base into ECR (pull-through cache) does NOT dodge the
VPN DNS failure alone - the build runs in the dev's buildkitd container, which
resolves via Docker's unreachable `8.8.8.8` fallback, so it would fail to
resolve the ECR hostname too. Stopping rebuilds is the durable win. User is
interested but explicitly deferred until the current feature is done.

## Related

- [[sources/obs-2026-08-05-pulumi-preview-for-seqauto-split-reads-2-in-scope-changes-9-]] -
  pre-deploy churn context.

---

_Observed: 2026-08-05T17:07:03.971Z_
