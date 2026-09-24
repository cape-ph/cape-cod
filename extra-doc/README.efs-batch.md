# EFS-backed AWS Batch capability

CAPE Cod can create an AWS Batch compute environment whose hosts mount one or
more EFS filesystems during bootstrap. This is a dormant capability. The
feature does not create an EFS filesystem, add a deployment route, or change a
current pipeline until a deployment configuration opts into it.

## Capability contract

A Batch environment opts into host bootstrap with a configuration shape like
this example:

```yaml
compute:
    environments:
        batch:
            - name: reference-data
              image: ami-xxxxxxxxxxxxxxxxx
              subnet_types:
                  - compute
              security_group_source: analysis
              host_bootstrap:
                  efs_mounts:
                      required: true
                      mounts:
                          - name: reference-data
                            fileSystemId: fs-xxxxxxxxxxxxxxxxx
                            mountPath: /mnt/reference_data
                            readOnly: true
                            tls: true
                            iam: true
              resources:
                  instance_types:
                      - m5.xlarge
                  min_vcpus: 0
                  desired_vcpus: 0
                  max_vcpus: 4
```

The example is documentation only. It is not active in the default dev stack.

`security_group_source` is useful when an existing security group already has
approved NFS access to the EFS mount targets. Without it, the Batch component
creates an environment-owned security group as it does for historical Batch
environments.

## AMI and bootstrap behavior

The host AMI must include the CAPE EFS mounter service. The merged AMI contract
uses these files:

```text
/etc/ecs/efs-mounts.json
/etc/ecs/efs-mounter.env
```

CAPE renders a MIME launch-template user-data document that atomically writes
those files before AWS Batch finishes ECS host setup. The bootstrap does not
restart ECS or the mounter early. The systemd dependency starts the mounter
after the Batch/ECS host configuration is ready.

Each mount entry declares:

- `fileSystemId`
- `mountPath`
- `readOnly`
- `tls`
- `iam`

The EFS filesystem must have mount targets in the Availability Zones used by
the Batch subnets. The mount-target security groups must allow NFS traffic from
the host security group. The instance role needs the EFS client permissions
required by the selected `iam` behavior.

## Dynamic child containers

A host mount does not automatically appear in dynamic AWS Batch child jobs.
The child job definition or Nextflow AWS Batch configuration must also expose
the host path as a container volume. For Nextflow this has the form:

```groovy
aws {
    batch {
        volumes = '/mnt/reference_data:/mnt/reference_data:ro'
    }
}
```

The parent container's EFS mount is not sufficient by itself.

## Nextflow path staging limitation

A host-mounted EFS path and a Nextflow `path` input are separate concerns. With
an S3-backed Nextflow work directory, Nextflow stages a `path` input from a
different filesystem into the S3 work directory and then into the child task.
A host volume does not disable that behavior. `stageInMode = 'symlink'` only
changes the task-side staging mode after the remote work-directory transfer.

Use this capability when a process consumes a stable mounted path directly or
when its execution model intentionally supports the mounted resource. Do not
assume that mounting EFS alone prevents a third-party Nextflow module from
copying a `path` input through S3.

## Operational boundaries

- Keep the EFS database or reference directory read-only for analysis jobs.
- Give each pipeline its own writable work directory and cleanup policy.
- Do not use one shared writable EFS work directory for concurrent pipelines.
- Validate mount-target placement, security-group ingress, IAM, TLS, and host
  readiness before routing a workload to the capability.
- Use a staged deployment and rollback plan when changing the AMI or EFS
  resource pointer.
- Keep physical filesystem IDs out of DAP fixtures and pipeline source.
