---
type: synthesis
title: "Pipeline Subsystem (capeinfra/pipeline/)"
slug: pipeline-subsystem
status: stable
confidence: high
created: 2026-07-13
updated: 2026-07-13
tags: ["pipeline", "etl", "glue", "batch", "airflow", "mwaa", "subsystem"]
---

# Pipeline Subsystem (`capeinfra/pipeline/`)

The data-and-analysis pipeline building blocks: ingest/transform (Glue
crawlers + ETL jobs), containerized analysis (ECR + AWS Batch), orchestration
(Apache Airflow via MWAA), and registries that catalog analysis pipelines and
workflows.

## Modules and constructs

- [[entities/pipeline-data-module]] - `DataCrawler` (AWS Glue crawler over
  buckets into a catalog database) and `EtlJob` (AWS Glue ETL job running a
  script from an S3 script bucket, source -> sink bucket).
- [[entities/airflow-module]] - `MwaaEnvironment` (managed Apache Airflow), plus
  helpers to grant Airflow pass-role/policy access to Batch compute environments
  and job definitions.
- [[entities/batch-module]] - `BatchCompute` (managed EC2 Batch compute
  environment + job queue) and `BatchJobDefinition` (container job definition
  referencing an ECR image).
- [[entities/ecr-module]] - `ContainerRepository` and `ContainerImage` (ECR
  repo + built images, via `pulumi_awsx`).
- [[entities/dap-registry-module]] - `DAPRegistry` (DynamoDB registry of data
  analysis pipelines, loaded from `assets/analysis-pipelines/` fixtures) and
  `WorkflowMetaRegistry` (DynamoDB store of Airflow workflow metadata).

## How it fits together

Tributaries in the data lake configure `DataCrawler`s and `EtlJob`s to catalog
and transform incoming data (see [[entities/datalake-module]]). Analysis
pipelines (e.g. bactopia) run as Nextflow/containerized jobs on AWS Batch, with
images in ECR; Airflow (MWAA) orchestrates workflows and is granted access to
Batch. The `DAPRegistry` and `WorkflowMetaRegistry` provide the metadata the
APIs query to list pipelines and schedule/inspect runs (see
[[entities/cape-rest-api-module]]). The `PrivateSwimlane` wires these together
(see [[entities/private-swimlane-module]]).

Note: Airflow workflows/DAGs themselves are deployed outside Pulumi (in the
`cape-cod-env` ansible repo); this subsystem only provisions the infrastructure
and metadata stores.

Related: [[syntheses/cape-cod-architecture-overview]],
[[syntheses/resources-subsystem]].
