# Rubber Duck Project - Developer Documentation

## Introduction

Welcome to the Rubber Duck Project! This documentation will guide you through the setup process and introduce you to the key technologies utilized in this project. The complete setup process is estimated to take approximately three hours. If you encounter significant issues during setup, please contact Dr. Bean for assistance.

## Initial Setup Requirements

Before proceeding, please provide the following information to Dr. Bean:

- GitHub username
- OpenAI account username
- Discord username
- BYU email address (required for AWS access)

## Technical Prerequisites

The following sections detail the technologies and systems required for the Rubber Duck Project. Please proceed through these sections sequentially to ensure proper configuration.

Each technology is essential for the project's functionality. If you are unfamiliar with any of these technologies, dedicated time during weekly research periods can be allocated for learning.

- Git and GitHub Project Management
- OpenAI Account Configuration
- Discord Bot Development
- Configuration File Customization
- Docker Containerization
- AWS CLI and Elastic Container Registry (ECR)

## Git and GitHub Project Management

1. **Repository Access**

   - Ensure that Dr. Bean has added you to the Bean Lab organization on GitHub
   - Verify your GitHub account for pending invitations from the Bean Lab organization
   - Access the Bean Lab organization at https://github.com/beanlab

2. **Project Repository Setup**
   - Clone the Rubber Duck repository using: `git clone https://github.com/beanlab/rubber-duck.git`
   - Navigate to the "Projects" tab in the repository to familiarize yourself with ongoing tasks and issues
   - Learn how to create issues and branches from the Projects tab
   - Document any feature or update information in appropriate issue tickets

## OpenAI Account Configuration

1. **Account Registration**

   - Register an account with OpenAI if you haven't already done so
   - Forward your OpenAI username to Dr. Bean for organizational access

2. **Organization Setup**
   - Monitor your email for an invitation to join the BYU Computer Science Bean Organization
   - Verify your organization settings and access the API Keys section
   - Generate a new secret key and store it securely
   - **Security Notice**: Never share your API key or expose it in version-controlled code. Use environment variables or secret management solutions to protect this sensitive information.

## Discord Bot Development

1. **Bot Configuration**
   - Complete the introductory assignment to configure a Discord Bot
   - Follow the instructions posted on Dr. Bean's WICS Build A Bot Server
   - Submit your completed bot to the "please-add-my-bot" channel

## Configuration File Customization

1. **Local Environment Setup**

   - Ensure you have cloned the repository to your local development environment
   - Locate the configuration file template in the repository

2. **Discord Channel Configuration**
   - Create dedicated bot and admin channels on the Bean Lab Discord server
     - Name format: `your-name-chat-bot` and `your-name-bot-admin`
   - Retrieve the channel IDs by right-clicking on each channel
   - Update the configuration file with:
     - Your bot's name in the config section
     - The server ID (found by right-clicking the server icon)
     - The appropriate channel IDs for your bot and admin channels
     - Your personal Discord ID in the reviewer_role_id and admin_role_id fields
   - Use appropriate labels for organizational clarity

## Docker Containerization (Optional)

This section is recommended for developers who have not previously worked with Docker. Docker is utilized in the Rubber Duck production environment to create deployment-ready applications.

1. **Docker Installation**

   - Follow the installation guide at: [Docker Desktop Setup](https://docs.docker.com/desktop/setup/install/windows-install/)
   - If you encounter startup issues with Docker Desktop, consider installing an earlier version from [Docker Release Notes](https://docs.docker.com/desktop/release-notes/#4150)

2. **Docker Learning Resources**
   - Watch the first 30 minutes of this [Docker Tutorial](https://youtu.be/fqMOX6JJhGo) and follow along with the examples
   - Verify your installation by running the Docker Hello-World container

## GitHub Secrets Configuration

The following secrets must be configured in your GitHub repository for proper CI/CD functionality:

| **Secret Name**            | **Description**                                                                                 | **Example Value**                                            |
| -------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| **AWS_ACCESS_KEY_ID**      | AWS Access Key ID for authenticating with AWS services.                                         | `AKIAIOSFODNN7EXAMPLE`                                       |
| **AWS_SECRET_ACCESS_KEY**  | AWS Secret Access Key corresponding to the above Access Key ID.                                 | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`                   |
| **AWS_REGION**             | AWS region where the resources will be created or accessed.                                     | `us-west-2`                                                  |
| **AWS_ACCOUNT_ID**         | AWS Account ID of the account where resources are managed.                                      | `844825014198`                                               |
| **ECR_REGISTRY**           | The AWS Elastic Container Registry (ECR) registry URI.                                          | `123456789012.dkr.ecr.us-west-2.amazonaws.com`               |
| **ECR_REPOSITORY**         | The name of the ECR repository.                                                                 | `my-app-repo`                                                |
| **ECS_CLUSTER_NAME**       | The name of the ECS cluster where the service runs.                                             | `my-cluster`                                                 |
| **ECS_SERVICE_NAME**       | The name of the ECS service running within the ECS cluster.                                     | `my-service`                                                 |
| **ENV_FILE_S3_PATH**       | The S3 path to the environment file that contains configuration settings.                       | `arn:aws:s3:::rubber-duck-config/wiley-secrets.env`          |
| **EXECUTION_ROLE**         | The ARN of the IAM role that allows ECS tasks to pull images and publish logs.                  | `arn:aws:iam::844825014198:role/ecsTaskExecutionRole`        |
| **IMAGE_URI**              | The URI of the Docker image stored in ECR.                                                      | `123456789012.dkr.ecr.us-west-2.amazonaws.com/my-app:latest` |
| **SECURITY_GROUP_ID**      | The ID of the security group that controls inbound and outbound traffic.                        | `sg-05cce821e162bca07`                                       |
| **SUBNET_IDS**             | Comma-separated list of subnet IDs within the VPC.                                              | `subnet-0a9cdc5582a7a6e20,subnet-1b8b9a9c87b1a6343`          |
| **TASK_DEFINITION_FAMILY** | The family of task definitions for ECS tasks.                                                   | `my-task-definition-family`                                  |
| **TASK_ROLE**              | The ARN of the IAM role that grants permissions for the ECS task to interact with AWS services. | `arn:aws:iam::844825014198:role/ecsTaskExecutionRole`        |
| **VPC_ID**                 | The ID of the Virtual Private Cloud (VPC) where your infrastructure resides.                    | `vpc-057175f829f9e74b2`                                      |

### Secret Categories and Purpose

1. **AWS Authentication**

   - The AWS credentials provide secure access to AWS services and should have only the necessary permissions for your deployment.

2. **AWS Account Information**

   - The Account ID and Region define the AWS environment for resource deployment.

3. **Container Registry**

   - ECR registry and repository details for container image storage and management.

4. **ECS Deployment Configuration**

   - Cluster and service names to identify the containerized application in AWS ECS.

5. **IAM Role Configuration**

   - Execution and task roles define the permissions for your ECS tasks to interact with other AWS services.

6. **Environment Configuration**

   - The S3 path provides access to environment variables and sensitive configuration data.

7. **Network Infrastructure**
   - VPC, subnet, and security group IDs define the networking environment for your ECS tasks.

### Security Best Practices

- Store all credentials in GitHub Secrets to prevent exposure in source code
- Implement least privilege principles for IAM roles and AWS credentials
- Maintain separate secrets for different deployment environments (staging, production)

## AWS Cloud Deployment Infrastructure

This section covers the AWS services required for the CI/CD deployment pipeline. Contact Dr. Bean if you need access to BYU AWS resources.

1. **Elastic Container Service (ECS)**

   - Configure a cluster, service, and task definition
   - Reference the `esc_setup.sh` file for task definition examples
   - Configure the following GitHub Secrets:
     - `CLUSTER_NAME`: The name of your ECS cluster
     - `SERVICE_NAME`: The name of your ECS service
     - `TASK_DEFINITION_FAMILY`: The name of your task definition family
     - `IMAGE_URI`: The URI for your Docker container image
     - `REGION`: The AWS region for deployment

2. **Simple Storage Service (S3)**

   - Create an S3 bucket for configuration and environment files
   - Ensure the bucket has appropriate permissions:
     ```
     "Action": "s3:GetObject",
     "Resource": "arn:aws:s3:::rubber-duck-config/*"
     ```
   - Configure `ENV_FILE_S3_PATH` with the ARN path to your environment file

3. **CloudWatch Integration**

   - Implement CloudWatch logging for application monitoring
   - Ensure your IAM user has the following permissions:
     ```
     "Action": ["logs:CreateLogStream", "logs:PutLogEvents"]
     ```

4. **Identity and Access Management (IAM)**
   - Create an execution role with the following policy attachments:
     - CloudWatch logging permissions
     - S3 object access permissions
     - ECR image pull permissions
   - Configure `EXECUTION_ROLE` with the ARN of your execution role

## Introductory Assignment

Complete the Discord bot creation assignment to ensure your environment is correctly configured:

1. Follow the instructions at: [Discord Instructions](https://discord.gg/YGRXPCCT)
2. Create and configure your Discord bot
3. Test the bot's functionality to verify your setup

## Bot Usage Documentation

The Rubber Duck bot monitors configured channels (default: "duck-pond") and creates threaded responses to user messages.

### Server Deployment

To deploy the bot on a server:

```bash
cd /path/to/project
git pull
poetry install
nohup poetry run python discord_bot.py >> /tmp/duck.log &
```

To terminate the bot process:

```bash
ps -e | grep python
kill <pid>
```

## Environment Configuration

### Config File Format

The configuration file for Rubber Duck is in JSON format and should include the following sections:

1. **Channels**: Defines the channels the bot monitors and their properties

   ```json
   "channels": {
     "duck-pond": {
       "name": "Duck Pond",
       "server_id": "123456789012345678",
       "channel_id": "123456789012345678"
     },
     "admin-channel": {
       "name": "Admin Channel",
       "server_id": "123456789012345678",
       "channel_id": "123456789012345678"
     }
   }
   ```

2. **Roles**: Defines the access permissions

   ```json
   "roles": {
     "admin_role_id": "123456789012345678",
     "reviewer_role_id": "123456789012345678"
   }
   ```

3. **Environment Variables**: Required for both local development and deployment
   - `DISCORD_TOKEN`: Authentication token for your Discord bot
   - `OPENAI_API_KEY`: API key for accessing OpenAI services
   - `CONFIG_FILE_S3_PATH`: For AWS deployment, path to config in S3 (format: `s3://bucket-name/path/to/config.json`)

### S3 Configuration

For proper S3 configuration:

1. Your config file should be uploaded to the specified S3 bucket
2. The bot expects JSON format for the configuration file
3. The S3 bucket must have appropriate permissions set
4. The `ENV_FILE_S3_PATH` should be in the format: `arn:aws:s3:::bucket-name/file-name.env`

## CI/CD Pipeline Details

The Rubber Duck project uses GitHub Actions for continuous integration and deployment to AWS. Understanding this pipeline is essential for efficient development and troubleshooting.

### Pipeline Overview

The workflow consists of two main jobs:

1. **Build and Push**:

   - Checks out the code
   - Sets up Docker build environment
   - Builds the Docker image using the build script
   - Configures AWS credentials
   - Logs in to Amazon ECR
   - Pushes the Docker image to ECR

2. **Deploy to CloudFormation**:
   - Deploys the ECS infrastructure using CloudFormation
   - Sets up the task definition with required parameters
   - Configures networking, roles, and environment

### CloudFormation Template

The CloudFormation template (`ecs-infra.yml`) defines the following resources:

1. **ECS Cluster**: Container management service
2. **CloudWatch Log Group**: Centralized logging
3. **Fargate Task Definition**: Container configuration
4. **ECS Service**: Service management and scaling

Parameters in the template include:

- Environment settings
- Resource naming
- Container configuration
- Networking details (VPC, subnets, security groups)
- IAM role configuration
- Environment file location

### Configuring the Pipeline

To modify the CI/CD pipeline:

1. Edit the `.github/workflows/ci-cd.yml` file
2. Update parameters in `infra/ecs-infra.yml` for infrastructure changes
3. Ensure all required GitHub Secrets are configured

## Troubleshooting Common Issues

### Environment File Issues

If your bot fails with errors like `NoSuchKey` or `FileNotFoundError`:

1. Verify the S3 path is correct in your GitHub Secrets
2. Confirm the file exists in the specified S3 location
3. Check IAM permissions for the task execution role
4. Inspect CloudWatch logs for detailed error messages

### Role Permission Issues

If you encounter permission errors:

1. Verify the execution role has policies for:
   - ECR image pulling (`ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, etc.)
   - CloudWatch logging (`logs:CreateLogStream`, `logs:PutLogEvents`)
   - S3 access (`s3:GetObject` for your bucket)
2. Check the role ARN format in GitHub Secrets

### Deployment Failures

If CloudFormation deployment fails:

1. Review the error messages from the GitHub Actions logs
2. Verify all parameter values are correctly set
3. Check for resource naming conflicts or existing stacks
4. Ensure all required parameters have values

## Local Testing Before Deployment

Before pushing changes to trigger the CI/CD pipeline:

1. **Local Bot Testing**:

   ```bash
   # Set environment variables
   export DISCORD_TOKEN=your_discord_token
   export OPENAI_API_KEY=your_openai_key

   # Run the bot
   poetry run python discord_bot.py --config your_config.json --log-console
   ```

2. **Docker Container Testing**:

   ```bash
   # Build the image locally
   docker build -t rubber-duck:test .

   # Run the container
   docker run -e DISCORD_TOKEN=your_token -e OPENAI_API_KEY=your_key rubber-duck:test
   ```

3. **Configuration Testing**:
   - Validate your JSON config file using a JSON validator
   - Test S3 access with the AWS CLI: `aws s3 cp s3://your-bucket/your-config.json ./`

## Development Best Practices

1. **Branching Strategy**:

   - Create feature branches from `master`
   - Use descriptive branch names (e.g., `feature/add-new-command`)
   - Create pull requests for review before merging

2. **Testing**:

   - Test changes locally before pushing
   - Monitor CloudWatch logs after deployment
   - Create test cases for new features

3. **Security**:

   - Never commit sensitive information (tokens, keys)
   - Use GitHub Secrets for all sensitive data
   - Follow least privilege principle for IAM roles

4. **Documentation**:
   - Document new features in the README
   - Update the configuration section when adding new options
   - Comment complex code sections
