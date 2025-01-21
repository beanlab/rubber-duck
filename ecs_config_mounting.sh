#!/bin/bash

# Variables - Update these to match your setup
set -e

TASK_FAMILY="rubber-duck-task-family"
CONTAINER_NAME="rubber-duck-container"
IMAGE_URI="844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:latest"
MEMORY="512"
CPU="256"
CONFIG_FILE_PATH="$(pwd)/config.json"
CONTAINER_CONFIG_PATH="/rubber-duck"

if [[ ! -f "$CONFIG_FILE_PATH" ]]; then
  echo "Error: Configuration file not found at $CONFIG_FILE_PATH"
  exit 1
fi

# Create the task definition JSON
cat <<EOF > task-definition.json
{
  "family": "$TASK_FAMILY",
  "containerDefinitions": [
    {
      "name": "$CONTAINER_NAME",
      "image": "$IMAGE_URI",
      "essential": true,
      "memory": $MEMORY,
      "cpu": $CPU,
      "mountPoints": [
        {
          "sourceVolume": "config-volume",
          "containerPath": "$CONTAINER_CONFIG_PATH"
        }
      ]
    }
  ],
  "volumes": [
    {
      "name": "config-volume",
      "host": {
        "sourcePath": "$CONFIG_FILE_PATH"
      }
    }
  ]
}
EOF

# Register the task definition
echo "Registering ECS Task Definition..."
if aws ecs register-task-definition --cli-input-json file://task-definition.json; then
  echo "Task Definition registered successfully!"
else
  echo "Failed to register Task Definition."
  rm task-definition.json
  exit 1
fi

# Clean up
rm task-definition.json

echo "Task Definition registered successfully."
