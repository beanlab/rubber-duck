# Deployment Guide

This guide covers the deployment process for the Rubber Duck bot to AWS infrastructure.

## Prerequisites

1. **AWS Account Access**

   - Ensure you have access to the BYU AWS account
   - Have the necessary IAM permissions

2. **AWS CLI**

   - Install AWS CLI from [aws.amazon.com/cli](https://aws.amazon.com/cli/)
   - Configure with your credentials

3. **Docker**
   - Install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop)
   - Verify installation with `docker --version`

## GitHub Secrets Configuration

The following secrets must be configured in your GitHub repository:

| Secret Name           | Description                 | Example                                             |
| --------------------- | --------------------------- | --------------------------------------------------- |
| AWS_ACCESS_KEY_ID     | AWS Access Key ID           | AKIAIOSFODNN7EXAMPLE                                |
| AWS_SECRET_ACCESS_KEY | AWS Secret Access Key       | wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY            |
| AWS_REGION            | AWS region                  | us-west-2                                           |
| VPC_ID                | VPC ID                      | vpc-057175f829f9e74b2                               |
| SUBNET_IDS            | Comma-separated subnet IDs  | subnet-0a9cdc5582a7a6e20,subnet-1b8b9a9c87b1a6343   |
| SECURITY_GROUP_ID     | Security Group ID           | sg-05cce821e162bca07                                |
| EXECUTION_ROLE        | ECS Task Execution Role ARN | arn:aws:iam::844825014198:role/ecsTaskExecutionRole |

## Deployment Process

1. **Build Docker Image**

   ```bash
   docker build -t rubber-duck:latest .
   ```

2. **Push to ECR**

   ```bash
   aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck
   docker tag rubber-duck:latest 844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:latest
   docker push 844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:latest
   ```

3. **Deploy to ECS**
   - The deployment is automated through GitHub Actions
   - Push to the master branch to trigger deployment
   - Monitor the deployment in GitHub Actions

## Configuration Files

1. **Environment Configuration**

   - Store environment variables in S3
   - Format: `s3://rubber-duck-config/pre-production/secrets-{sha}.env`

2. **Bot Configuration**
   - JSON configuration in S3
   - Format: `s3://rubber-duck-config/pre-production/config-{sha}.json`

## Monitoring

1. **CloudWatch Logs**

   - View logs in AWS CloudWatch
   - Log group: `/ecs/rubber-duck-pre-production`

2. **ECS Service**
   - Monitor service health in ECS console
   - Check task status and logs

## Troubleshooting

1. **Deployment Failures**

   - Check GitHub Actions logs
   - Verify all secrets are configured
   - Ensure IAM roles have correct permissions

2. **Container Issues**

   - Check CloudWatch logs
   - Verify environment variables
   - Ensure config files are accessible

3. **Network Issues**
   - Verify VPC and subnet configuration
   - Check security group rules
   - Ensure proper IAM roles

## Rollback Procedure

1. **Manual Rollback**

   ```bash
   # Revert to previous image
   aws ecs update-service --cluster DuckCluster-rubber-duck-pre-production --service rubber-duck-pre-production-Service --force-new-deployment
   ```

2. **GitHub Rollback**
   - Revert the commit that caused issues
   - Push to trigger new deployment

## Best Practices

1. **Security**

   - Never commit sensitive information
   - Use GitHub Secrets for all credentials
   - Follow least privilege principle

2. **Deployment**

   - Test in pre-production first
   - Monitor deployment progress
   - Have rollback plan ready

3. **Monitoring**
   - Set up CloudWatch alarms
   - Monitor error rates
   - Track resource utilization
