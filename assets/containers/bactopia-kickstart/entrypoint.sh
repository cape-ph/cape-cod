#!/bin/bash
set -ex

# Placeholder assignments simply to track what environment variables to expect

PIPELINE_URL=${PIPELINE_URL}
PIPELINE_VERSION=${PIPELINE_VERSION}
# if pipeline url is provided but no script, assume main.nf
if [[ -n ${PIPELINE_URL} ]]; then
    PIPELINE=${PIPELINE:-main.nf}
    unset PIPELINE_VERSION
fi
if [[ -n ${PIPELINE_VERSION} ]]; then
    PIPELINE_VERSION="-r ${PIPELINE_VERSION}"
fi
NF_OPTS=${NF_OPTS}

# Get AWS Region if not already set
if [[ -z ${AWS_REGION} ]]; then
    AWS_REGION=$(curl --silent "${ECS_CONTAINER_METADATA_URI}" | jq -r '.Labels["com.amazonaws.ecs.task-arn"]' | awk -F: '{print $4}')
fi

# If pipeline URL not provided, make an empty scratch directory
if [[ -z ${PIPELINE_URL} ]]; then
    mkdir -p /scratch
# If pipeline URL is an s3 path, pull it to a scratch directory
elif [[ "${PIPELINE_URL}" =~ ^s3://.* ]]; then
    aws s3 cp --recursive "${PIPELINE_URL}" /scratch
# Assume any other pipeline URL is a git path, clone to a scratch directory
else
    # Assume it is a git repository
    git clone "${PIPELINE_URL}" /scratch
fi

cd /scratch

# sanitize BUCKET_NAME
BUCKET_NAME_RESULTS=$(echo "${BUCKET_NAME_RESULTS}" | sed -e 's#s3://##')

# Make temporary bucket for work directory
BUCKET_TEMP_NAME=nextflow-spot-batch-temp-${AWS_BATCH_JOB_ID}
aws --region "${AWS_REGION}" s3 mb s3://"${BUCKET_TEMP_NAME}"

nextflow run "${PIPELINE}" ${PIPELINE_VERSION} -profile aws -work-dir s3://"${BUCKET_TEMP_NAME}" ${NF_OPTS}
