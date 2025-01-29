#!/bin/bash

source .env
# Variables
CLUSTER_NAME="DuckCluster"
SERVICE_NAME="DuckService"
TASK_DEFINITION_FAMILY="Deploy-Duck"
IMAGE_URI="844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:latest"  # Docker image in ECR
S3_ENV_FILE=$ENV_FILE_S3_PATH # get this from the settings.txt
REGION="us-west-2"
AWS_ACCOUNT_ID="844825014198"
EXECUTION_ROLE="arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole"

# Set the desired CPU and memory for the task definition
CPU="1024"
MEMORY="2048"

# Step 1: Register the ECS Task Definition
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
      "environment": [
          {
              "name": "$CONFIG_FILE_NAME",
              "value": "s3://rubber-duck-config/$CONFIG_FILE_S3_PATH"
          }
      ],
      "environmentFiles": [
        {
          "value": "$S3_ENV_FILE",
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

# Register Task Definition
echo "$TASK_DEFINITION_JSON" | aws ecs register-task-definition --cli-input-json file://- --region $REGION

# Step 2: Update the ECS Service
echo "Updating ECS service with new task definition..."
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --task-definition $TASK_DEFINITION_FAMILY \
  --desired-count 1 \
  --force-new-deployment \
  --region $REGION

echo "Deployment completed successfully!"
