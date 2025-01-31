#!/bin/bash


CLUSTER_NAME="DuckCluster"
SERVICE_NAME="DuckService"
TASK_DEFINITION_FAMILY="Deploy-Duck"
IMAGE_URI="844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:latest"
REGION="us-west-2"
AWS_ACCOUNT_ID="844825014198"
EXECUTION_ROLE="arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole"
ENV_FILE_S3_PATH=s3://rubber-duck-config/wiley-secrets.env

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

# Register Task Definition
echo "$TASK_DEFINITION_JSON" | aws ecs register-task-definition --cli-input-json file://- --region $REGION

# Step 5: Update the ECS Service
echo "Updating ECS service with new task definition..."
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --task-definition $TASK_DEFINITION_FAMILY \
  --desired-count 1 \
  --force-new-deployment \
  --region $REGION

echo "Deployment completed successfully!"
