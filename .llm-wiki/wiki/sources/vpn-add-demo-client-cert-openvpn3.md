---
type: source
title: Adding a demo VPN client cert with easyrsa + openvpn3
status: insight
category: devops
created: 2026-08-18
updated: 2026-08-18
slug: vpn-add-demo-client-cert-openvpn3
---

# Adding a demo VPN client cert with easyrsa + openvpn3

Procedure for adding a throwaway client cert/key pair to the CAPE private-swimlane VPN without touching the server pair, CA, or existing client entries. Complements [[extra-doc/README.vpn.md]] which documents the `openvpn` CLI; this system only has `openvpn3`.

## Environment
- easyrsa env: `/home/lp76/easyrsa-envs/cape-cod` (run easyrsa from inside it so it uses `./pki`).
- Installed easyrsa is `3.2.5` (README was tested against `3.2.0`). Signing a new client against the existing CA is unaffected.
- CA is `CN=cape-cod.dev`; server is `CN=server`. Existing client pairs: `cape-dev.org`, `*.cape-dev.org`, `true.cape-dev.org`.
- Both openvpn3 configs `cape-vpn` and `cape-split` authenticate with client `CN=cape-dev.org`. `cape-vpn` is the plain endpoint profile; `cape-split` is the split-DNS variant.

## Build a new client pair
- `easyrsa build-client-full <name> nopass` prompts for interactive `yes` confirmation and aborts (rolling back the req/key) if not answered. Use `easyrsa --batch build-client-full <name> nopass` to sign non-interactively.
- Dots in the CN are fine (existing certs use them). Example name used: `demo-2026.08`, cert valid 825 days.
- New files land beside the others: `pki/issued/<name>.crt`, `pki/private/<name>.key`, `pki/reqs/<name>.req`, plus one appended row in `pki/index.txt`. 3.2.5 writes these `0600` vs the older `0644`.

## Build the .ovpn on an openvpn3-only host
- Reuse the trusted endpoint profile instead of a fresh AWS console download: `openvpn3 config-dump --config cape-vpn > base.ovpn`, then swap only the `<cert>` and `<key>` blocks for the new pair, leaving `<ca>` and the `remote ...:443` line identical. Do NOT use `cape-split` as the base unless split-DNS is wanted.
- Extract a clean cert PEM with `openssl x509 -in issued/<name>.crt` (strips easyrsa's extra text); the `nopass` key file is already a clean `BEGIN PRIVATE KEY` block.
- Verify the key belongs to the cert by comparing `openssl pkey -pubout | openssl dgst -sha256` against `openssl x509 -noout -pubkey | openssl dgst -sha256`. Note MD5 is disabled on this OpenSSL 3.5 build, so an MD5 modulus check silently returns empty strings that falsely "match" - use sha256.
- Keep profiles in `~/.openvpn3cfg/cape/`, named for the client pair. Remove any temp copies of key material from `/tmp` afterward.

## Import / connect / revoke
- Import under a distinct name so it doesn't collide: `openvpn3 config-import --config <file> --name cape-vpn-demo --persistent`.
- Connect: `openvpn3 session-start --config cape-vpn-demo`; disconnect: `openvpn3 session-manage --config cape-vpn-demo --disconnect`.
- A new cert authenticates immediately because it shares the CA the endpoint trusts and has no CRL entry. Endpoint-side authorization is a separate concern from cert validity.
- Revoke when done: `easyrsa revoke <name>` then `easyrsa gen-crl`, then import the CRL `.pem` at the VPC Client VPN endpoint (Actions -> Import client certificate CRL). Keeping the openvpn3 config around lets you retest that revocation actually blocks the client.

*Category: devops*

---
*Captured: 2026-08-18*

## Related

_Add links to related pages._
