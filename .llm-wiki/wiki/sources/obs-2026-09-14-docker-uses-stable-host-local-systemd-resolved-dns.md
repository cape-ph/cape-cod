---
type: source
title: "Observation: Docker uses stable host-local systemd-resolved DNS"
tags:
  - docker
  - dns
  - systemd-resolved
  - pulumi
  - nextflow
  - deployment
status: observation
created: 2026-09-14
updated: 2026-09-14
slug: obs-2026-09-14-docker-uses-stable-host-local-systemd-resolved-dns
relevance: high
observed_at: 2026-09-14T17:46:02.457Z
source_context: Fix Docker Hub DNS failure during Pulumi Nextflow image build
---

# ⭐ Observation: Docker uses stable host-local systemd-resolved DNS

Installed `/etc/systemd/resolved.conf.d/docker-dns.conf` with `DNSStubListenerExtra=172.17.0.1` and `/etc/docker/daemon.json` with Docker DNS `172.17.0.1`. Restarted systemd-resolved and Docker. Verified systemd-resolved listens on the Docker bridge gateway, `dig @172.17.0.1 registry-1.docker.io` resolves, Docker daemon is healthy, and `docker pull amazoncorretto:21.0.8` succeeds. This avoids hard-coding VPN resolver IPs: systemd-resolved selects current VPN or physical-link upstream DNS dynamically. The Pulumi image update still requires the user to rerun `pulumi up`; no Pulumi deploy was run by the agent.

*Relevance: high*
*Context: Fix Docker Hub DNS failure during Pulumi Nextflow image build*
*Tags: docker dns systemd-resolved pulumi nextflow deployment*

---
*Observed: 2026-09-14T17:46:02.457Z*
