# Build the Python Tools Execution Environment Docker
set -e # Exit immediately if a command exits with a non-zero status.

IMAGE_NAME="byucscourseops/python-tools-sandbox"
IMAGE_TAG="latest"

docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t ${IMAGE_NAME}:${IMAGE_TAG} \
    --push \
    -f - . <<EOF

# Base image
FROM python:3.12-slim

# Setup working directory
WORKDIR /app

# Copy helper script
COPY run_code.py /app/run_code.py

# Install allowed Python libraries
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    statsmodels \
    tabulate

# Create a non-root user for security
RUN useradd -m sandbox
USER sandbox

EOF

docker pull ${IMAGE_NAME}:${IMAGE_TAG}
