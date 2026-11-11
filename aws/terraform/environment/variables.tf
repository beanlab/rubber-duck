variable "aws_account_id" {
  description = "AWS account that owns the environment."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must contain 12 digits."
  }
}

variable "region" {
  description = "AWS region for the environment."
  type        = string
}

variable "environment" {
  description = "Canonical deployment environment name."
  type        = string

  validation {
    condition     = contains(["production"], var.environment)
    error_message = "Only the explicitly mapped production environment is supported."
  }
}

variable "state_bucket" {
  description = "S3 state bucket consumed by deployment tooling."
  type        = string
}

variable "state_key" {
  description = "Environment-specific Terraform state key consumed by deployment tooling."
  type        = string
}

variable "vpc_id" {
  description = "Existing private VPC ID."
  type        = string
}

variable "subnet_id" {
  description = "Existing private subnet ID."
  type        = string
}

variable "availability_zone" {
  description = "Availability zone shared by the subnet and persistent data volume."
  type        = string
}

variable "ami_id" {
  description = "Explicitly pinned official Canonical Ubuntu AMI ID."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t3.small"
}

variable "root_volume_size_gib" {
  description = "Replaceable EC2 root volume size."
  type        = number
  default     = 20
}

variable "data_volume_size_gib" {
  description = "Persistent SQLite data volume size."
  type        = number
  default     = 30
}

variable "ecr_repository_name" {
  description = "Existing ECR repository name."
  type        = string
}

variable "configuration_bucket" {
  description = "Existing application configuration bucket."
  type        = string
}

variable "runtime_s3_prefixes" {
  description = "Existing S3 buckets and exact key patterns referenced by production configuration."
  type        = map(set(string))
  default     = {}
}

variable "ses_sender_identity" {
  description = "Verified SES sender identity used for registration email."
  type        = string
}

variable "permissions_boundary_arn" {
  description = "Required enterprise IAM permissions boundary."
  type        = string
}
