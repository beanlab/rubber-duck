variable "aws_account_id" {
  description = "AWS account that owns the deployment resources."
  type        = string
}

variable "region" {
  description = "AWS region for deployment resources."
  type        = string
  default     = "us-west-2"
}

variable "state_bucket" {
  description = "S3 bucket used for Terraform state and native lock files."
  type        = string
}

variable "github_repository" {
  description = "GitHub owner/repository allowed to assume the deployment role."
  type        = string
  default     = "beanlab/rubber-duck"
}

variable "ecr_repository_name" {
  description = "Existing ECR repository used by Rubber Duck."
  type        = string
  default     = "beanlab/rubber-duck"
}

variable "permissions_boundary_arn" {
  description = "Required enterprise IAM permissions boundary."
  type        = string
}
