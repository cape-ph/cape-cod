---
type: analysis
title: CAPE pipeline execution classes and resource capabilities
created: 2026-09-18
updated: 2026-09-23
status: follow-on-design
---

# CAPE pipeline execution classes and resource capabilities

Status: follow-on design reference as of the Issue 379 checkpoint. The current
branch uses the concrete `general-analysis` and `taxonomic-profiling` execution
classes, while the zero-to-many capability/resource model remains future work.
This page is included because it documents the logical execution terminology
used by the current route. EFS implementation details remain separately owned
by PR 385 and issues 381/380; this page is not deployment approval.

## Problem

CAPE currently catalogs DAP profiles under `assets/analysis-pipelines/`, while Pulumi config defines Batch compute environments under the private swimlane. There is no binding from a DAP to the Batch environment capabilities required by its run. `BatchCompute` models hardware, AMI, networking, and vCPU capacity, but not host-mounted volume capabilities.

A dynamic child can land on any eligible host in the selected Batch compute environment. A host-path volume is valid only when that host has the corresponding resource mounted and ready. A parent ECS-managed EFS mount does not propagate to dynamic children.

## Desired contract

The platform should support zero or many resource dependencies for a pipeline. A dependency may be a database, a large reference dataset, or another shared resource. Physical AWS IDs must not appear in DAP fixtures or pipeline source.

A future DAP contract may use a logical execution class and logical resource references:

```json
{
    "execution": {
        "framework": "nextflow",
        "class": "taxonomic-profiling"
    },
    "resourceDependencies": {
        "volumes": [
            {
                "ref": "taxonomic-reference-data",
                "mountPath": "/mnt/cape/taxonomy",
                "readOnly": true
            }
        ]
    }
}
```

The resource resolver maps logical references to current physical resources, mount paths, access points, and security requirements. A changed EFS filesystem ID should require a registry/deployment update, not a DAP or pipeline change.

## Execution classes

A compute environment configuration should eventually have a sibling logical execution-class mapping. A class can identify the framework, queue or compute-environment class, host capabilities, resource policy, and supported volume backends.

The initial terminology is:

- `taxonomic-profiling` - the workload execution class for Kraken2, Bracken, MetaPhlAn, and related taxonomic tools.
- `taxonomic-reference-data` - a logical volume/resource reference. It is not tied to Kraken2 or to EFS in the DAP contract.

A future Snakemake adapter should consume the same logical dependencies while translating them into its own execution path.

## Volume backends

### Host-mounted EFS bridge

The near-term migration may use a host-mounted EFS bridge. A host mounter or systemd service consumes a runtime registry, mounts the current resource at a stable path, and keeps eligible hosts ready before work is accepted. Nextflow continues using host-path volume mappings.

This is a tactical bridge. It requires a placement/readiness policy because a Batch child may land on any host in the queue. Mounting the union of every possible volume on every host is not the desired final behavior.

### ECS-managed child volumes

A direct ECS-managed EFS child volume would attach the logical resource in each dynamic child job definition. This better expresses per-job dependencies, but current Nextflow `aws.batch.volumes` creates host-path volumes and does not create `efsVolumeConfiguration`. Supporting this path requires an upstream executor change, a maintained fork, or a CAPE-owned submission layer. It is a larger follow-on and is not assumed for the current cutover.

## Design questions

- Should execution classes select a queue directly, or should a resolver select a compatible class from capability requirements?
- How does the platform ensure that a host is mount-ready before Batch schedules a child?
- Which registry stores logical resource references and current physical IDs?
- How are mount updates drained when an EFS resource is replaced?
- Are dependencies pipeline-wide or scoped to selected processes?
- How are read-only, read-write, access-point, UID/GID, TLS, and IAM requirements represented?
- How are zero-volume pipelines kept on the general execution path?
- How do Nextflow and future Snakemake adapters consume the same contract?

## Non-goals for the current Bactopia cutover

- Redesign all Batch queues and compute environments.
- Own a Nextflow or nf-amazon fork.
- Implement arbitrary capability-aware scheduling.
- Add a general resource registry before the immediate taxprofiler path works.
- Make S3 database staging the default without cost and performance evidence.

## Relationship to the current migration

The Bactopia v4.1 migration should use the smallest supported tactical path that avoids repeated large database transfers. It must document the bridge and its limits, preserve logical naming, and leave the generic execution-class/resource model as a separately tracked follow-on.

Related: [[analyses/bactopia-41-cape-cod-implementation-design]]
