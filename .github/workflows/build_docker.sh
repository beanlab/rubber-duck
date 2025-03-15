#!/bin/bash

# Fetch the Git commit hash for the tag
IMAGE_NAME="rubber-duck"
IMAGE_TAG=${GITHUB_SHA:-$(git rev-parse HEAD)} # Use GitHub SHA if available, otherwise git hash

# Get branch name from GitHub context or git command
if [ -n "$GITHUB_REF" ]; then
  BRANCH_NAME=${GITHUB_REF#refs/heads/}
else
  BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
fi

# Sanitize branch name for Docker tag (remove slashes, etc.)
SAFE_BRANCH_NAME=$(echo "$BRANCH_NAME" | tr '/' '-' | tr -cd '[:alnum:]-')

# Create combined tag with branch name and abbreviated SHA
COMBINED_TAG="${SAFE_BRANCH_NAME}-${IMAGE_TAG:0:7}"

ECR_REPO="844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck"

echo "Building Docker image with combined tag: ${COMBINED_TAG}"

set -e

# Build the Docker image
docker build -t ${IMAGE_NAME}:${COMBINED_TAG} .

# Tag image for ECR
docker tag ${IMAGE_NAME}:${COMBINED_TAG} ${ECR_REPO}:${COMBINED_TAG}

# Only add production-latest tag for master branch
if [[ "$BRANCH_NAME" == "master" ]]; then
  docker tag ${IMAGE_NAME}:${COMBINED_TAG} ${ECR_REPO}:production-latest
  echo "Also tagged as production-latest"
fi

echo "Docker image tagged as: ${ECR_REPO}:${COMBINED_TAG}"

