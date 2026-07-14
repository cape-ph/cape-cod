---
type: source
title: "Pointing /etc/resolv.conf at systemd-resolved stub fixes Go-resolver and openvpn3 split-DNS"
slug: systemd-resolved-stub-fixes-go-resolver-and-openvpn3-split-dns
status: insight
created: 2026-07-14
updated: 2026-07-14
category: devops
---
# Pointing /etc/resolv.conf at systemd-resolved stub fixes Go-resolver and openvpn3 split-DNS
On a Fedora/RHEL-family laptop running multiple VPNs (GTRI openconnect `tun0` full-tunnel, plus an AWS Client VPN via openvpn3 for the CAPE `cape-dev.org` VPC), DNS for VPN-only names silently failed until `/etc/resolv.conf` was pointed at the systemd-resolved stub.

Root cause (single, shared across two symptoms): NetworkManager was in `rc-manager` foreign mode and wrote uplink nameservers directly into `/etc/resolv.conf` instead of the resolved stub `127.0.0.53`. systemd-resolved was running with correct per-link split-DNS, but clients that read `/etc/resolv.conf` directly bypassed it.

- Symptom 1: Pulumi (a Go binary) could not resolve `*.amazonaws.com` on the GTRI VPN. Go's pure resolver reads `/etc/resolv.conf` directly and ignores the nsswitch `resolve` module, so it queried the GT nameservers which were unreachable over the full-tunnel default route. Python/libc apps (aws-adfs, browser, curl) worked because nsswitch routed them through resolved.
- Symptom 2: openvpn3 could not resolve private `cape-dev.org` names even though `netcfg.json` already had `"systemd_resolved": true`. netcfg registered the VPC resolvers on the tun link correctly, but clients read the NM-written `/etc/resolv.conf` and never consulted resolved.

Fix (persistent): set NetworkManager `dns=systemd-resolved` in `/etc/NetworkManager/conf.d/dns.conf` and reload NM, which symlinks `/etc/resolv.conf` -> `/run/systemd/resolve/stub-resolv.conf`. This fixed both symptoms at once; no openvpn3 change was needed.

Verified working state with AWS Client VPN up: openvpn3 creates `tun1` with VPC resolvers `10.0.123.80`/`10.0.250.117` and DNS routing domain `~.`, routes only `10.0.0.0/16` via `tun1` (split tunnel from `pull-filter ignore "redirect-gateway"` + `route 10.0.0.0 255.255.0.0` in `aws-cvpn-endpoint.ovpn`), leaves the default route on the work VPN, and `analysis-pipelines.cape-dev.org` resolves to `10.0.x` and returns HTTP 200. The work VPN `tun0` (`gtri.org`) coexists.

openvpn3 operational notes: services run as user `openvpn`, netcfg is D-Bus-activated as root; unprivileged users start/stop their own sessions with `openvpn3 session-start --config <file>` / `openvpn3 session-manage --config <file> --disconnect` / `openvpn3 sessions-list`. netcfg DNS backend lives in `/var/lib/openvpn3/netcfg.json` and is set with `openvpn3-admin netcfg-service --config-set systemd-resolved`.

Diagnostic tips: `dig` with no `@server` reads `/etc/resolv.conf` (bypasses resolved); use `resolvectl query`, `getent hosts`, or `dig @127.0.0.53` to test the resolved path. On a full-tunnel work VPN, `dig @8.8.8.8` may time out because corporate policy blocks outbound 53 - not proof a name is unresolvable.
*Category: devops*
---
*Captured: 2026-07-14*
## Related
_Add links to related pages._