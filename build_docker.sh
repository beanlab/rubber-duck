#!/bin/bash

# Fetch the Git commit hash or branch name to create a unique tag
IMAGE_NAME="rubber-duck"
IMAGE_TAG=$(git rev-parse --abbrev-ref HEAD) # Use branch name

ECR_REPO="844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck"

set -e

# Build the Docker image
cd ../../
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -f - ../../ <<EOF
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

# Tag the image for ECR with the unique tag (commit hash or branch name)
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REPO}:${IMAGE_TAG}

# Conditional logic for testing or production
if [[ "$IMAGE_TAG" == "master" ]]; then
    # Production tag
    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REPO}:production-latest
    echo "Tagging as production-latest"
else
    # Test tag
    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REPO}:test-latest
    echo "Tagging as test-latest"
fi

# Push both tags to ECR
docker push ${ECR_REPO}:${IMAGE_TAG}
docker push ${ECR_REPO}:test-latest
docker push ${ECR_REPO}:production-latest

echo "Push complete!"
