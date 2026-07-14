---
type: source
title: "Observation: Dual-VPN split-DNS fix: scope AWS Client VPN to cape-dev.org via dns-scope tunnel + dhcp-option DOMAIN"
slug: obs-2026-07-14-dual-vpn-split-dns-fix-scope-aws-client-vpn-to-cape-dev-org-
status: observation
created: 2026-07-14
updated: 2026-07-14
relevance: high
observed_at: 2026-07-14T17:15:58.967Z
tags: ["dns", "vpn", "openvpn3", "systemd-resolved", "split-dns", "cape", "networking"]
source_context: "Making GTRI VPN and AWS Client VPN coexist so gitlab.gtri.gatech.edu and cape-dev.org both work simultaneously"
---
# ⭐ Observation: Dual-VPN split-DNS fix: scope AWS Client VPN to cape-dev.org via dns-scope tunnel + dhcp-option DOMAIN
Fixed the dual-VPN DNS collision where gitlab.gtri.gatech.edu failed whenever both the GTRI VPN (openconnect tun0) and AWS Client VPN (openvpn3 tun1) were connected. Root cause: openvpn3 defaults to dns-scope=global for the AWS VPN, which registers the systemd-resolved routing domain "~." (catch-all) on tun1. Since tun0 only claimed "gtri.org", the "~." out-matched it for gitlab.gtri.gatech.edu (not under gtri.org), sending the query to the AWS VPC resolver (10.0.123.80) which returns NXDOMAIN. The GTRI resolver (10.41.107.129) resolves it to CNAME gitlab-east.gtri.gatech.edu -> 18.254.106.211.

Fix (AWS-side scoping): (1) In aws-cvpn-endpoint.ovpn add `dhcp-option DOMAIN cape-dev.org` (the private VPC zone; from Pulumi.cape-cod-dev.yaml `domain: cape-dev.org`, covers all subdomains api/jupyterhub/opa/analysis-pipelines). (2) `dns-scope tunnel` CANNOT go in the .ovpn - openvpn3 rejects it as UNKNOWN/UNSUPPORTED OPTION and the connection fails. It must be a config override on a named persistent config. Also `dhcp-option DOMAIN-ROUTE` from the client config was NOT honored (tun1 got no domains); `dhcp-option DOMAIN` IS mapped to a systemd-resolved domain. (3) config-import has no --force; to update you must config-remove --force then re-import.

Working setup:
  openvpn3 config-remove --config cape-aws --force   # if already imported
  openvpn3 config-import --config aws-cvpn-endpoint.ovpn --name cape-aws --persistent
  openvpn3 config-manage --config cape-aws --dns-scope tunnel
  openvpn3 session-start --config cape-aws            # MUST start by NAME, not file path
  openvpn3 session-manage --config cape-aws --disconnect

Critical workflow change: start the AWS VPN BY NAME (cape-aws). Starting by file path (session-start --config <file>) imports transiently with dns-scope=global, so "~." returns and gitlab breaks again. Result: tun0 owns gtri.org, tun1 owns only cape-dev.org, 10.0.0.0/16 routes via tun1, gitlab resolves via GTRI, cape-dev.org via AWS, public via GTRI/system. Add more private zones with additional `dhcp-option DOMAIN-SEARCH <zone>` lines then re-import; verify with `resolvectl domain`. Backup at aws-cvpn-endpoint.ovpn.bak.
*Relevance: high*

*Context: Making GTRI VPN and AWS Client VPN coexist so gitlab.gtri.gatech.edu and cape-dev.org both work simultaneously*

*Tags: dns vpn openvpn3 systemd-resolved split-dns cape networking*
---
*Observed: 2026-07-14T17:15:58.967Z*