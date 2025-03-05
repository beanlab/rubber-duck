#!/bin/bash

# Fetch the Git commit hash or branch name to create a unique tag
IMAGE_NAME="rubber-duck"
IMAGE_TAG=$(git rev-parse --abbrev-ref HEAD)  # using branch name as tag

ECR_REPO="844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck"

set -e

# Change to the repository root
cd ../../

# Build the Docker image using the repository root ('.') as the build context
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -f - . <<EOF
FROM python:3.11.9
LABEL authors="Wiley Welch, Bryce Martin, Gordon Bean"
COPY rubber_duck /rubber_duck
COPY prompts /prompts
ADD pyproject.toml /rubber_duck/pyproject.toml
WORKDIR /rubber_duck
RUN pip install poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi
EXPOSE 8080
WORKDIR /
CMD ["python", "/rubber_duck/discord_bot.py", "--config", "/config.json", "--log-console"]
EOF

# Tag the image for ECR with the unique tag (branch name)
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REPO}:${IMAGE_TAG}

# Also tag as "latest" for easier reference (and optionally as "latest-latest" if needed)
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REPO}:latest
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REPO}:latest-latest

