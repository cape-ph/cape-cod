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
PIPELINE_QUEUE=${PIPELINE_QUEUE}
NF_OPTS=${NF_OPTS}
NEXTFLOW_AWS_BATCH_CLI_PATH=${NEXTFLOW_AWS_BATCH_CLI_PATH}
NEXTFLOW_PROCESS_OVERRIDES=${NEXTFLOW_PROCESS_OVERRIDES}

# The parent container CLI is used for entrypoint operations. The Nextflow
# cliPath value must identify the AWS CLI on the Batch host AMI.
PARENT_AWS_CLI_PATH=$(command -v aws)
if [[ -z ${PARENT_AWS_CLI_PATH} ]]; then
    echo "AWS CLI not found on the parent container PATH" >&2
    exit 1
fi
if [[ -z ${NEXTFLOW_AWS_BATCH_CLI_PATH} ]]; then
    echo "Batch host AWS CLI path is not configured" >&2
    exit 1
fi
if [[ "${NEXTFLOW_AWS_BATCH_CLI_PATH}" != /*/bin/aws ]]; then
    echo "Batch host AWS CLI path must end with /bin/aws" >&2
    exit 1
fi

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

# Make temporary bucket for work directory
BUCKET_TEMP_NAME=nextflow-spot-batch-temp-${AWS_BATCH_JOB_ID}
aws --region "${AWS_REGION}" s3 mb s3://"${BUCKET_TEMP_NAME}"

# TODO: allow user to pass in a specific nextflow config string and use that
# instead, evaluating environment variables with something like
# `${NEXTFLOW_CONFIG@P} (requires bash v4.4+)
cat >/nextflow.config <<EOF
process {
    executor = 'awsbatch'
    queue = '${PIPELINE_QUEUE}'
    // symlink kraken data - THIS SHOULD BE MOVED TO PIPELINE SPECIFIC NEXTFLOW CONFIG
    withName: '.*:KRAKEN2|KRAKEN2' {
        stageInMode = 'symlink'
    }
EOF

if [[ -n ${NEXTFLOW_PROCESS_OVERRIDES} ]]; then
    if ! jq -e 'type == "object" and all(.[]; type == "object" and (.selector | type == "string") and (.cpus | type == "number") and (.memory | type == "string") and (.time | type == "string"))' <<<"${NEXTFLOW_PROCESS_OVERRIDES}" >/dev/null; then
        echo "Invalid validated Nextflow process override policy" >&2
        exit 1
    fi
    while IFS=$'\t' read -r selector cpus memory time; do
        cat >>/nextflow.config <<EOF
    withName: '${selector}' {
        cpus = ${cpus}
        memory = ${memory}
        time = ${time}
    }
EOF
    done < <(jq -r 'to_entries[] | [.value.selector, (.value.cpus | tostring), .value.memory, .value.time] | @tsv' <<<"${NEXTFLOW_PROCESS_OVERRIDES}")
fi

cat >>/nextflow.config <<EOF
}
aws {
    region = '${AWS_REGION}'
    batch {
        cliPath = '${NEXTFLOW_AWS_BATCH_CLI_PATH}'
    }
}
EOF

# Execute Nextflow
# TODO: remove bactopia cachedir environment variable? We would have to move it
# somewhere but it doesn't pose any issues with other workflows for now
BACTOPIA_CACHEDIR=s3://${BUCKET_TEMP_NAME} nextflow \
    run "${PIPELINE}" ${PIPELINE_VERSION} \
    -c /nextflow.config \
    -work-dir s3://"${BUCKET_TEMP_NAME}"/work \
    ${NF_OPTS}

# Cleanup
# Empty temporary bucket
aws --region "${AWS_REGION}" s3 rm s3://"${BUCKET_TEMP_NAME}" --recursive
# Remove temporary bucket
aws --region "${AWS_REGION}" s3 rb s3://"${BUCKET_TEMP_NAME}"
