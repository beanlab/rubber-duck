#!/bin/bash

TASK_FAMILY="rubber-duck-task-family"
CONTAINER_NAME="rubber-duck-container"
IMAGE_URI="844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:latest"
MEMORY="512"
CPU="256"
CONFIG_FILE_PATH="$(pwd)/config.json"
CONTAINER_CONFIG_PATH="/rubber-duck"
ENV_FILE_PATH="/rubber-duck/secrets.env"  # Path where secrets.env will be downloaded

# Check for config.json
if [[ ! -f "$CONFIG_FILE_PATH" ]]; then
  echo "Error: Configuration file not found at $CONFIG_FILE_PATH"
  exit 1
fi

# Download the .env file from S3
echo "Downloading secrets.env from S3..."
aws s3 cp s3://rubber-duck-config/secrets.env $ENV_FILE_PATH

# Check if secrets.env was downloaded successfully
if [[ ! -f "$ENV_FILE_PATH" ]]; then
  echo "Error: secrets.env file not found after download."
  exit 1
fi

# Create the task definition JSON
cat <<EOF > task-definition.json
{
  "family": "$TASK_FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": [
    "FARGATE"
  ],
  "cpu": "$CPU",
  "memory": "$MEMORY",
  "ephemeralStorage": {
    "sizeInGiB": 21
  },
  "runtimePlatform": {
    "cpuArchitecture": "X86_64",
    "operatingSystemFamily": "LINUX"
  },
  "containerDefinitions": [
    {
      "name": "$CONTAINER_NAME",
      "image": "$IMAGE_URI",
      "cpu": 0,
      "memory": "$MEMORY",
      "essential": true,
      "command": [
        "sh",
        "-c",
        "source /rubber-duck/secrets.env && python3 /rubber_duck/discord_bot.py"
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/Deploy-Duck",
          "awslogs-create-group": "true",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "executionRoleArn": "arn:aws:iam::844825014198:role/ecsTaskExecutionRole",
  "status": "ACTIVE",
  "compatibilities": [
    "EC2",
    "FARGATE"
  ],
  "placementConstraints": [],
  "tags": []
}
EOF

# Register the task definition with ECS
echo "Registering task definition..."
TASK_DEFINITION_ARN=$(aws ecs register-task-definition \
  --cli-input-json file://task-definition.json \
  --query "taskDefinition.taskDefinitionArn" \
  --output text)

echo "Task definition registered successfully: $TASK_DEFINITION_ARN"

# Clean up
rm task-definition.json
