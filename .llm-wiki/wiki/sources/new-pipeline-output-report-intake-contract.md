---
type: source
title: New pipeline output-report intake contract
status: insight
category: architecture
created: 2026-09-25
updated: 2026-09-25
slug: new-pipeline-output-report-intake-contract
---

# New pipeline output-report intake contract

Before adding a new pipeline output through CAPE Cod, collect seven inputs: (1) pipeline identity, version, execution owner, target stack, and completion marker; (2) logical tributary plus exact S3 bucket and output-prefix pattern; (3) a successful-run object tree and representative sanitized files; (4) canonical sample, run, and input-object identifiers with a mapping example; (5) desired clean CSV schemas, Athena table names, partition keys, normalization, and example queries; (6) report ID, data sections, joins, HTML/PDF requirements, and a template or mock; and (7) isolated validation data, crawler timing, external orchestration steps, and deployment-preview scope. Physical bucket names are validation inputs, not values to hard-code in profiles or ETL. The implementation seam is the existing [[entities/pipeline-data-module]] ETL/crawler chain plus [[entities/assets-report]] data-function/template pair and the generic `/report/create` route. Credentials and secrets should never be included in the packet.

*Category: architecture*

---
*Captured: 2026-09-25*

## Related

_Add links to related pages._
