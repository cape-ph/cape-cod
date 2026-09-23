---
type: source
title: "Observation: EC2 test instance has failed reachability and historical Java OOM"
tags:
  - ec2
  - health
  - oom
  - nextflow
  - bactopia
  - testing
status: observation
created: 2026-09-15
updated: 2026-09-15
slug: obs-2026-09-15-ec2-test-instance-has-failed-reachability-and-historical-jav
relevance: critical
observed_at: 2026-09-15T20:22:01.018Z
source_context: EC2 status and Bactopia v4.1 test diagnosis
---

# 🔴 Observation: EC2 test instance has failed reachability and historical Java OOM

The standalone EC2 instance `i-01274bddc155993e8` is currently running but its EC2 instance reachability check has been failed since `2026-09-15T20:09:00Z`; system reachability and attached EBS checks pass. The instance type is `t3.micro` with 1 GiB memory. Its console output records the Linux OOM killer terminating a Java process (`Out of memory: Killed process ... java`). This likely explains SSH instability and makes the long Bactopia v4.1 QC timing/results unreliable. The skip-QC-plots resume did not yield a result before SSH loss. Resize or restore instance health before resuming the Bactopia tests.

*Relevance: critical*
*Context: EC2 status and Bactopia v4.1 test diagnosis*
*Tags: ec2 health oom nextflow bactopia testing*

---
*Observed: 2026-09-15T20:22:01.018Z*
