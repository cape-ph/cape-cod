---
type: source
title: "Observation: openvpn3 is the documented CAPE VPN client, not openvpn 2.x"
tags:
  - vpn
  - docs
  - openvpn3
  - easyrsa
status: observation
created: 2026-08-18
updated: 2026-08-18
slug: obs-2026-08-18-openvpn3-is-the-documented-cape-vpn-client-not-openvpn-2-x
relevance: medium
observed_at: 2026-08-18T17:35:02.076Z
source_context: Updating README.vpn.md for easy-rsa 3.2 and openvpn3
---

# 🔍 Observation: openvpn3 is the documented CAPE VPN client, not openvpn 2.x

The openvpn 2.x CLI path in extra-doc/README.vpn.md has not been tested in a long time (per repo maintainer). PR #378 (branch 377-docsvpn-update-readme-vpn-for-easyrsa-32-and-openvpn3, issue #377) makes openvpn3 the documented VPN client throughout the README and reduces openvpn 2.x to a passing "may work but not covered" mention. Connect flow is now openvpn3 config-import / session-start / sessions-list / session-manage --disconnect. Do not re-add the openvpn 2.x `openvpn --config` instructions as a primary path.

*Relevance: medium*
*Context: Updating README.vpn.md for easy-rsa 3.2 and openvpn3*
*Tags: vpn docs openvpn3 easyrsa*

---
*Observed: 2026-08-18T17:35:02.076Z*
