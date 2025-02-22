# Build Rubber Duck Docker
# this is the command to build the docker image
# ./build_docker.sh
# TODO make image_tag dynamic based on the git commit we are trying to deploy.

IMAGE_NAME="rubber-duck"
IMAGE_TAG="latest"
ECR_REPO="844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck"

docker build \
    -t ${IMAGE_NAME}:${IMAGE_TAG} \
    -f - . <<EOF
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

# Tag the image for ECR
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REPO}:${IMAGE_TAG}
