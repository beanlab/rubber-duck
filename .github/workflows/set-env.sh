#!/bin/bash

# Extract the branch name from GitHub Actions (or fallback to local git branch)
if [ -n "$GITHUB_REF" ]; then
    BRANCH_NAME="${GITHUB_REF#refs/heads/}"
else
    BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
fi

echo "Branch name: $BRANCH_NAME"

# Set environment variables based on branch
if [[ "$BRANCH_NAME" == "master" ]]; then
    ENVIRONMENT="production"
    IMAGE_TAG="latest"
else
    ENVIRONMENT="test"
    IMAGE_TAG="test-latest"
fi

echo "Deployment Environment: $ENVIRONMENT"
echo "Image Tag: $IMAGE_TAG"

# If running in GitHub Actions, write to $GITHUB_ENV
if [ -n "$GITHUB_ENV" ]; then
    echo "ENVIRONMENT=$ENVIRONMENT" >> $GITHUB_ENV
    echo "IMAGE_TAG=$IMAGE_TAG" >> $GITHUB_ENV
fi
