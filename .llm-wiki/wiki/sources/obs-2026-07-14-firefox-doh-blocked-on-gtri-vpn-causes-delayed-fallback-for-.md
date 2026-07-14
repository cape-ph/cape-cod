---
type: source
title: "Observation: Firefox DoH blocked on GTRI VPN causes delayed fallback for private names"
slug: obs-2026-07-14-firefox-doh-blocked-on-gtri-vpn-causes-delayed-fallback-for-
status: observation
created: 2026-07-14
updated: 2026-07-14
relevance: high
observed_at: 2026-07-14T16:17:55.969Z
tags: ["dns", "vpn", "firefox", "doh", "systemd-resolved", "networking"]
source_context: "Troubleshooting Firefox not resolving private AWS Client VPN (cape-dev.org) names while on GTRI VPN"
---
# ⭐ Observation: Firefox DoH blocked on GTRI VPN causes delayed fallback for private names
On the GTRI + AWS dual-VPN laptop setup, Firefox failed to resolve private VPN names (analysis-pipelines.cape-dev.org) then intermittently "started working" after a delay. Root cause: Firefox profile jurpx7jm.default-release has doh-rollout.mode=2 (TRR-first, Cloudflare DoH). The GTRI full-tunnel VPN blocks public DoH endpoints - curl to https://mozilla.cloudflare-dns.com/dns-query and https://dns.google/resolve both time out (10s) while systemd-resolved (getent) resolves the name instantly. So Firefox tries DoH first, times out, marks TRR failed, then falls back to the OS resolver - that fallback is the observed delay, and it recurs on every TRR re-confirmation (network change, VPN reconnect), making it fragile. Deterministic fix: set network.trr.mode=5 (DoH off) so Firefox always uses systemd-resolved, which already does correct split-DNS across tun0 (gtri.org) and tun1 (~. -> AWS VPC resolver 10.0.123.80/10.0.250.117). Chrome uses the OS resolver and was unaffected. General principle: OS-level systemd-resolved split-DNS is the reliable layer; apps that do their own DNS (Go pure resolver via /etc/resolv.conf, Firefox DoH) must be pointed back at the OS resolver.
*Relevance: high*

*Context: Troubleshooting Firefox not resolving private AWS Client VPN (cape-dev.org) names while on GTRI VPN*

*Tags: dns vpn firefox doh systemd-resolved networking*
---
*Observed: 2026-07-14T16:17:55.969Z*