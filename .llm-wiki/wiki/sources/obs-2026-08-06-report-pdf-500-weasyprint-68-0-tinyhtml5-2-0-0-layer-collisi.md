---
type: source
title: "Observation: Report PDF 500 = weasyprint 68.0/tinyhtml5 2.0.0 layer collision + encoding arg; PDF also exceeds 29s API GW cap"
slug: obs-2026-08-06-report-pdf-500-weasyprint-68-0-tinyhtml5-2-0-0-layer-collisi
status: observation
created: 2026-08-06
updated: 2026-08-06
relevance: high
observed_at: 2026-08-06T20:14:42.546Z
tags: ["cape-cod", "reports", "weasyprint", "tinyhtml5", "lambda-layers", "pdf", "apigateway", "timeout", "diagnosis"]
source_context: "Diagnosing canned-report PDF 500 + client timeout for the bactopia report endpoint"
---
# ⭐ Observation: Report PDF 500 = weasyprint 68.0/tinyhtml5 2.0.0 layer collision + encoding arg; PDF also exceeds 29s API GW cap
Diagnosed (not fixed) the CAPE canned-report PDF failures for the getcannedreport handler (ccd-pvsl-capi-api-getcannedreport-lmbdfn-b295d26, python3.13, memory 128MB, timeout 60s; behind private REST API rm7re3p9e1 stage capi-dev, GET /report/create, integration timeoutInMillis=29000). HTML format works (200); PDF returns 500 with 'HTMLUnicodeInputStream.__init__() got an unexpected keyword argument override_encoding'. Root cause = weasyprint/tinyhtml5 version collision from two layers: report-gen:21 ships weasyprint 66.0 + tinyhtml5 2.1.0 under /opt/python; kotify-cpu:5 (gh-release tag weasyprint-68.0) ships weasyprint 68.0 + tinyhtml5 2.0.0 under /opt/python/lib/python3.13/site-packages plus the system libs/fonts. weasyprint 66.0 does NOT pass override_encoding for a string source; weasyprint 68.0 always forwards override_encoding when encoding is set. tinyhtml5 2.1.0's HTMLUnicodeInputStream.__init__(self, source, **kwargs) absorbs it; 2.0.0's __init__(self, source) rejects it. The error can ONLY come from weasyprint 68.0 + tinyhtml5 2.0.0 (the kotify pair won on sys.path). Trigger: get_canned_report.py calls weasyprint.HTML(string=report_html, encoding='utf-8'); that encoding arg is redundant for an already-decoded string and is what forwards override_encoding. HTML works because its branch never calls weasyprint. Fix options (not applied): drop encoding= from the HTML() call, or stop shipping two weasyprints / bump kotify tag so bundled tinyhtml5>=2.1.0. Separately, the client timeout memory is real: API Gateway REST caps at 29s; the data function's serial Athena queries already make the HTML path ~24.8s at 110/128MB used, so PDF rendering (Pango/Cairo/fontconfig) at the CPU-throttled 128MB tier exceeds 29s -> client 504 even though Lambda timeout is 60s. Handler TODO already wants async generate-store-notify. Also note: private API DNS does not resolve off-VPN (curl timed out on resolution); on the ClientVPN the execute-api hostname should resolve.
*Relevance: high*

*Context: Diagnosing canned-report PDF 500 + client timeout for the bactopia report endpoint*

*Tags: cape-cod reports weasyprint tinyhtml5 lambda-layers pdf apigateway timeout diagnosis*
---
*Observed: 2026-08-06T20:14:42.546Z*