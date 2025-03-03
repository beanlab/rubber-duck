#!/bin/bash

if [ "$#" -ne 7 ]; then
    echo "Usage: $0 <CLUSTER_NAME> <SERVICE_NAME> <TASK_DEFINITION_FAMILY> <IMAGE_URI> <REGION> <EXECUTION_ROLE> <ENV_FILE_S3_PATH>"
    exit 1
fi

# Assign arguments to variables
CLUSTER_NAME="$1"
SERVICE_NAME="$2"
TASK_DEFINITION_FAMILY="$3"
IMAGE_URI="$4"
REGION="$5"
EXECUTION_ROLE="$6"
ENV_FILE_S3_PATH="$7"

# Set the desired CPU and memory for the task definition
CPU="1024"
MEMORY="2048"

echo "Registering new ECS Task Definition..."
TASK_DEFINITION_JSON=$(cat <<EOF
{
  "family": "$TASK_DEFINITION_FAMILY",
  "executionRoleArn": "$EXECUTION_ROLE",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "Rubber_Duck",
      "image": "$IMAGE_URI",
      "cpu": 0,
      "memory": $MEMORY,
      "portMappings": [],
      "essential": true,
      "environment": [],
      "environmentFiles": [
        {
          "value": "$ENV_FILE_S3_PATH",
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
          "awslogs-region": "$REGION",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "$CPU",
  "memory": "$MEMORY",
  "ephemeralStorage": {
    "sizeInGiB": 21
  },
  "runtimePlatform": {
    "cpuArchitecture": "X86_64",
    "operatingSystemFamily": "LINUX"
  }
}
EOF
)

NEW_TASK_DEFINITION=$(echo "$TASK_DEFINITION_JSON" | aws ecs register-task-definition --cli-input-json file://- --region $REGION --query 'taskDefinition.taskDefinitionArn' --output text)

echo "Updating ECS service with new task definition..."
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --task-definition $NEW_TASK_DEFINITION \
  --desired-count 1 \
  --force-new-deployment \
  --region $REGION

echo "Deployment completed successfully!"