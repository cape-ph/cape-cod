---
type: source
title: "Observation: Implemented cape-cod ABAC resource export (capeinfra/authz/export.py + stack output)"
slug: obs-2026-07-14-implemented-cape-cod-abac-resource-export-capeinfra-authz-ex
status: observation
created: 2026-07-14
updated: 2026-07-14
relevance: high
observed_at: 2026-07-14T15:14:05.378Z
tags: ["abac", "resource-export", "pulumi", "cape-cod", "implemented", "datalake", "export"]
source_context: "Implementing cape-cod ABAC resource export"
---
# ⭐ Observation: Implemented cape-cod ABAC resource export (capeinfra/authz/export.py + stack output)
Implemented the cape-cod ABAC resource export (per the filed plan). Files: (1) capeinfra/authz/__init__.py + capeinfra/authz/export.py - pure builders _category_for_bucket_id, _display_label, _resource_record, _assemble_export, plus _collect_export_inputs (runtime-free tributary/bucket iteration) and build_resource_export(dlh, stack)->Output[dict]; emits plain dicts, NO cape_cod_db dependency (O1 decision). (2) capeinfra/datalake/datalake.py Tributary.__init__ now captures self.code=config.get('name'), self.display_name=config.get('display_name', default=code), self.description=config.get('description', default=None). (3) __main__.py adds pulumi.export('abac_resource_export', build_resource_export(capeinfra.data_lakehouse, capeinfra.CAPE_STACK_NS)). (4) .mise.toml task 'export-abac-resources' runs `pulumi stack output abac_resource_export --json > cape-cod-export.json`. (5) tests/test_authz_export.py - 10 tests, all pass. Export shape: {version:"1.0", pulumi_stack, tributaries:[{code,name,description,resources:[{resource_type:"s3", resource_identifier:"s3://<real-bucket>/", display_name, attributes:{bucket,arn,category,bucket_role,tributary_code,environment,managed_by:"cape-cod-pulumi"}}]}]}. category map: input-raw->raw_uploads, input-clean->clean_uploads, result-raw->raw_results, result-clean->clean_results, else 'other' (logged warn). No access_type, no grants (catalog only). Verified: 10/10 pytest pass, ruff clean at 80 cols, runtime import + pure-function behavior confirmed. black/isort not installed and no network to fetch; pi-lens auto-format applied their style and ruff covers import order/line length.
*Relevance: high*

*Context: Implementing cape-cod ABAC resource export*

*Tags: abac resource-export pulumi cape-cod implemented datalake export*
---
*Observed: 2026-07-14T15:14:05.378Z*