---
type: source
title: EC2 Bactopia test instance OOM and reachability
status: insight
category: devops
created: 2026-09-15
updated: 2026-09-15
slug: ec2-bactopia-test-instance-oom-and-reachability
---

# EC2 Bactopia test instance OOM and reachability

The standalone test instance `i-01274bddc155993e8` is a `t3.micro` with 1 GiB memory. AWS reports it running but instance reachability has failed since `2026-09-15T20:09:00Z`; system and EBS reachability pass. EC2 console output contains a kernel OOM event that killed a Java process. The long Bactopia v4.1 QC run with `--skip_qc_plots` lost SSH access and produced no result, so its timing cannot be trusted as a workflow failure. Resize or restore instance health before resuming. The EC2 launcher needs enough memory for the Nextflow JVM even though child analysis tasks run in AWS Batch.

*Category: devops*

---
*Captured: 2026-09-15*

## Related

_Add links to related pages._
