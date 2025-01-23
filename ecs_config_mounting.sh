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
{
    "taskDefinitionArn": "arn:aws:ecs:us-west-2:844825014198:task-definition/Deploy-Duck:1",
    "containerDefinitions": [
        {
            "name": "Rubber_Duck",
            "image": "844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:latest",
            "cpu": 0,
            "memory": 2048,
            "portMappings": [],
            "essential": true,
            "environment": [],
            "environmentFiles": [
                {
                    "value": "arn:aws:s3:::rubber-duck-config/secrets.env",
                    "type": "s3"
                }
            ],
            "mountPoints": [],
            "volumesFrom": [],
            "ulimits": [],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/Deploy-Duck",
                    "mode": "non-blocking",
                    "awslogs-create-group": "true",
                    "max-buffer-size": "25m",
                    "awslogs-region": "us-west-2",
                    "awslogs-stream-prefix": "ecs"
                },
                "secretOptions": []
            },
            "systemControls": []
        }
    ],
    "family": "Deploy-Duck",
    "executionRoleArn": "arn:aws:iam::844825014198:role/ecsTaskExecutionRole",
    "networkMode": "awsvpc",
    "revision": 1,
    "volumes": [],
    "status": "ACTIVE",
    "requiresAttributes": [
        {
            "name": "com.amazonaws.ecs.capability.logging-driver.awslogs"
        },
        {
            "name": "ecs.capability.execution-role-awslogs"
        },
        {
            "name": "com.amazonaws.ecs.capability.ecr-auth"
        },
        {
            "name": "com.amazonaws.ecs.capability.docker-remote-api.1.19"
        },
        {
            "name": "com.amazonaws.ecs.capability.docker-remote-api.1.28"
        },
        {
            "name": "ecs.capability.env-files.s3"
        },
        {
            "name": "ecs.capability.execution-role-ecr-pull"
        },
        {
            "name": "ecs.capability.extensible-ephemeral-storage"
        },
        {
            "name": "com.amazonaws.ecs.capability.docker-remote-api.1.18"
        },
        {
            "name": "ecs.capability.task-eni"
        },
        {
            "name": "com.amazonaws.ecs.capability.docker-remote-api.1.29"
        }
    ],
    "placementConstraints": [],
    "compatibilities": [
        "EC2",
        "FARGATE"
    ],
    "requiresCompatibilities": [
        "FARGATE"
    ],
    "cpu": "1024",
    "memory": "2048",
    "ephemeralStorage": {
        "sizeInGiB": 21
    },
    "runtimePlatform": {
        "cpuArchitecture": "X86_64",
        "operatingSystemFamily": "LINUX"
    },
    "registeredAt": "2025-01-21T17:30:15.573Z",
    "registeredBy": "arn:aws:sts::844825014198:assumed-role/AWSReservedSSO_PowerUser-844825014198_2147179ec3f9c89a/wjw37@byu.edu",
    "enableFaultInjection": false,
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
