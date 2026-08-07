---
type: source
title:
    "Observation: Issue #366 findings: kotify weasyprint-69.0 is self-consistent
    + current; weasyprint 66/68 have CVEs, Pillow non-reachable on report path"
slug: obs-2026-08-07-issue-366-findings-kotify-weasyprint-69-0-is-self-consistent
status: observation
created: 2026-08-07
updated: 2026-08-07
relevance: high
observed_at: 2026-08-07T14:50:45.070Z
tags:
    [
        "cape-cod",
        "reports",
        "weasyprint",
        "kotify",
        "cloud-print-utils",
        "pillow",
        "cve",
        "osv",
        "lambda-layers",
        "issue-366",
        "pdf",
        "security-audit",
    ]
source_context:
    "Issue #366 investigation: kotify release check + report-path dependency/CVE
    audit"
---

# ⭐ Observation: Issue #366 findings: kotify weasyprint-69.0 is self-consistent + current; weasyprint 66/68 have CVEs, Pillow non-reachable on report path

Read-only investigation for issue #366 (weasyprint layer dedup) on
cape-ph/cape-cod. Findings posted as a comment on issue #366
(<https://github.com/cape-ph/cape-cod/issues/366#issuecomment-5218506876>).

Kotify cloud-print-utils has a self-consistent, current release: tag
weasyprint-69.0 (2026-06-25), asset weasyprint-layer-python3.13-x86_64.zip.
Bundle: weasyprint 69.0 + tinyhtml5 2.1.0 (matched pair, so the
override_encoding TypeError cannot occur), pydyf 0.12.1, tinycss2 1.5.1,
cssselect2 0.9.0, fonttools 4.63.0, cffi 2.0.0, pyphen 0.17.2, Pillow 12.2.0.
Native libs (gdk-pixbuf, gio, girepository) and DejaVu fonts still included.
Latest kotify weasyprint tag is 69.0; also offers a matching ghostscript-10.07.1
layer.

CVE audit via OSV API (PyPI ecosystem), report path = capi-all (capepy 3.0.0) +
report-gen (Jinja2 3.1.6, weasyprint 66.0) + kotify weasyprint bundle:

- weasyprint 66.0 (report-gen): CVE-2025-68616, CVE-2026-49452 (VULNERABLE)
- weasyprint 68.0 (kotify:5 current): CVE-2026-49452 (VULNERABLE)
- weasyprint 69.0 (kotify latest): clean
- Pillow 12.1.0 (kotify 68 bundle): ~19 CVEs; Pillow 12.2.0 (kotify 69 bundle):
  ~13 CVEs; Pillow 12.3.0 (PyPI latest + report-gen transitive): clean
- capepy 3.0.0, Jinja2 3.1.6, tinyhtml5 2.0.0/2.1.0, tinycss2 1.5.1, cffi
  2.0.0/2.1.1, fonttools 4.61.1/4.63.0, pydyf 0.12.1: all clean. capepy and
  Jinja2 already at PyPI latest.

Pillow reachability: all Pillow findings are raster image-decode bugs. The
bactopia-single-sample-analysis template.html.j2 embeds no raster images (only
solid CSS colors: #fff / oklch(); no <img>, url(), or base64), so weasyprint
never invokes Pillow decoders on this report. Pillow CVEs are effectively
non-reachable on this path; patch on principle, not an active exposure.

Pillow mitigation deferred (out of scope for #366): the fix leaves Pillow
vulnerable and relies solely on the non-reachability above. CONDITIONAL
FOLLOW-UP: this rationale holds only while report templates contain no raster
image formats. If a future template (e.g. an official report template) is
introduced that embeds a raster image - <img> with png/jpeg/gif/bmp/tiff, a CSS
url() raster, or base64-embedded raster data - the bundled Pillow version must
be re-checked against OSV/CVEs at that time and flagged as an active exposure if
still vulnerable, because weasyprint would then invoke Pillow's decoders on
rendered content. (weasyprint renders SVG with its own renderer, so SVG-only
templates do not trigger Pillow.)

sys.path precedence caveat: in this deployment kotify's site-packages resolves
AHEAD of report-gen's /opt/python. Proof: the observed PDF 500 was weasyprint
68.0 + tinyhtml5 2.0.0, both from the kotify bundle, meaning kotify won over
report-gen's 66.0. Therefore a dedup that relies on report-gen shadowing kotify
is NOT reliable here.

Recommended fix shape for #366: (1) bump kotify tag 68.0 -> 69.0 (clears
weasyprint CVEs + fixes tinyhtml5 collision at source); (2) drop weasyprint from
assets/lambda-layers/report-gen/requirements.txt so kotify is the single Python
weasyprint source, keeping Jinja2==3.1.6 (kotify does not bundle Jinja2); (3)
fully-clean Pillow would need a future kotify release bundling 12.3.0 or a
native-libs-only repackage (strip python/ from the kotify asset, keep
lib/+fonts/, provide weasyprint 69.0 + Pillow 12.3.0 via report-gen) - low
urgency given non-reachability. Validate after deploy with a PDF render
returning 200 + valid PDF. #366 is code-independent but not deploy-independent
(needs its own pulumi up + PDF check); intended as a new branch off main. Only
weasyprint consumer in the repo is assets/api/capi/handlers/get_canned_report.py
(data_function.py only mentions it in a comment); report-gen layer is attached
to exactly the getcannedreport handler. _Relevance: high_

_Context: Issue #366 investigation: kotify release check + report-path
dependency/CVE audit_

_Tags: cape-cod reports weasyprint kotify cloud-print-utils pillow cve osv
lambda-layers issue-366 pdf security-audit_
---

_Observed: 2026-08-07T14:50:45.070Z_
