# Build Rubber Duck Docker
# this is the command to build the docker image
# ./build_docker.sh

IMAGE_NAME="rubber-duck"
IMAGE_TAG="latest"

docker build \
    -t ${IMAGE_NAME}:${IMAGE_TAG} \
    -f - . <<EOF
FROM python:3.11.9
LABEL authors="Wiley Welch, Bryce Martin, Gordon Bean"
COPY rubber_duck /rubber_duck
ADD pyproject.toml /rubber_duck/pyproject.toml
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
WORKDIR /rubber_duck
RUN pip install poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi
CMD ["python", "/rubber_duck/discord_bot.py", "--config", "/config.json", "--log-console"]
EOF

# Tag the image for ECR
docker tag ${IMAGE_NAME}:${IMAGE_TAG} 844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:${IMAGE_TAG}
