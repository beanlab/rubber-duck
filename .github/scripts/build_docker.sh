#!/bin/bash

# Fetch the Git commit hash for the tag
IMAGE_NAME="rubber-duck"
IMAGE_TAG=${GITHUB_SHA:-$(git rev-parse HEAD)} # Use GitHub SHA if available, otherwise git hash

ECR_REPO="844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck"

echo "Building Docker image for ${IMAGE_NAME}:${IMAGE_TAG}..."

set -e

# Build the Docker image
docker build -t ${IMAGE_NAME}:latest -f - . <<EOF
FROM python:3.11.9
LABEL authors="Gordon Bean"
COPY src /app/src
COPY prompts /app/prompts
COPY datasets /app/datasets
ADD pyproject.toml /app/pyproject.toml
WORKDIR /app
RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Set up Python path
ENV PYTHONPATH=/app/src

CMD ["python", "-m", "src.main", "--config", "/config.json"]
EOF

# Tag the image for ECR with both latest and commit SHA
docker tag ${IMAGE_NAME}:latest ${ECR_REPO}:${IMAGE_TAG}
docker tag ${IMAGE_NAME}:latest ${ECR_REPO}:latest

# Conditional logic for testing or production
if [[ "${GITHUB_REF:-$(git rev-parse --abbrev-ref HEAD)}" == "refs/heads/master" ]]; then
    # Production tag
    docker tag ${IMAGE_NAME}:latest ${ECR_REPO}:production-latest
    echo "Tagging as production-latest"
else
    # Test tag
    docker tag ${IMAGE_NAME}:latest ${ECR_REPO}:test-latest
    echo "Tagging as test-latest"
fi

