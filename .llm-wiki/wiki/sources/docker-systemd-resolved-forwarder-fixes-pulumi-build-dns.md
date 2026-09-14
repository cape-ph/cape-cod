---
type: source
title: Docker systemd-resolved forwarder fixes Pulumi build DNS
status: insight
category: devops
created: 2026-09-14
updated: 2026-09-14
slug: docker-systemd-resolved-forwarder-fixes-pulumi-build-dns
---

# Docker systemd-resolved forwarder fixes Pulumi build DNS

Docker image builds failed because the Docker bridge attempted to resolve `registry-1.docker.io` through `8.8.4.4`, which timed out, while the host resolved through dynamic VPN DNS. The stable fix installed `/etc/systemd/resolved.conf.d/docker-dns.conf` with `DNSStubListenerExtra=172.17.0.1` and `/etc/docker/daemon.json` with `{"dns":["172.17.0.1"]}`. After restarting systemd-resolved and Docker, `dig @172.17.0.1 registry-1.docker.io` succeeded and `docker pull amazoncorretto:21.0.8` completed. The local forwarder remains active off VPN and follows systemd-resolved's current upstream DNS selection, avoiding hard-coded VPN resolver addresses. The user must rerun `pulumi up`; the agent did not deploy.

*Category: devops*

---
*Captured: 2026-09-14*

## Related

_Add links to related pages._
