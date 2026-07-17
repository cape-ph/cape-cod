---
type: entity
title: "certs module (capeinfra/resources/certs.py)"
slug: certs-module
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["acm", "tls", "certificates", "resources"]
---

# certs module (`capeinfra/resources/certs.py`)

## `BYOCert(CapeComponentResource)`

"Bring your own cert" wrapper around `aws.acm.Certificate`, created from local
PEM files rather than ACM-managed issuance.

- `type_name` = `capeinfra:resources:certs:BYOCert`.
- `BYOCert.from_config(name, tls_cfg, desc_name=None)` (staticmethod) - builds a
  cert from a TLS config dict with keys `dir`, `ca-cert`, `server-key`,
  `server-cert`. Raises `ValueError` on missing/invalid config or unreadable
  files.
- Constructor `BYOCert(name, ca_path, cert_path, key_path, ...)` - reads the
  three PEM files with `file_as_string` (raising `FileNotFoundError` if missing)
  and creates the ACM certificate with `certificate_chain`, `private_key`, and
  `certificate_body`.

TLS asset files are sensitive and are expected to live outside version control
(the repo ignores `assets-untracked/`; see `README.md` "Secret Asset Management"
and `extra-doc/README.vpn.md`). Carries code TODOs referencing ISSUE #99 and
ISSUE #125.

Used for swimlane domain certificates and ALB listeners (see
[[entities/scoped-swimlane-module]], [[entities/loadbalancer-module]]). Depends
on `file_as_string` from [[entities/util-modules]].

Related: [[syntheses/resources-subsystem]],
[[concepts/capepulumi-base-classes]].
