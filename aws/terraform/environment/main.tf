terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    cloudinit = {
      source  = "hashicorp/cloudinit"
      version = "~> 2.3"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Application = "rubber-duck"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_availability_zone" "selected" {
  name = var.availability_zone
}

data "aws_ami" "ubuntu" {
  most_recent = false
  owners      = ["099720109477"]

  filter {
    name   = "image-id"
    values = [var.ami_id]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

data "aws_ecr_repository" "application" {
  name = var.ecr_repository_name
}

data "aws_s3_bucket" "configuration" {
  bucket = var.configuration_bucket
}

data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_security_group" "instance" {
  name        = "${var.environment}-rubber-duck-no-ingress"
  description = "Rubber Duck production host: no ingress, outbound only"
  vpc_id      = var.vpc_id

  egress {
    description = "Required outbound application and management access"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ebs_volume" "data" {
  availability_zone = data.aws_availability_zone.selected.name
  encrypted         = true
  size              = var.data_volume_size_gib
  type              = "gp3"

  tags = {
    Name = "${var.environment}-rubber-duck-data"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_secretsmanager_secret" "runtime" {
  name                    = "/rubber-duck/${var.environment}/runtime"
  description             = "Runtime environment values for ${var.environment} Rubber Duck"
  recovery_window_in_days = 7
}

resource "aws_iam_role" "instance" {
  name                 = "${var.environment}-rubber-duck-instance"
  assume_role_policy   = data.aws_iam_policy_document.assume_ec2.json
  permissions_boundary = var.permissions_boundary_arn
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "runtime" {
  name = "${var.environment}-rubber-duck-runtime"
  role = aws_iam_role.instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuthorization"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "EcrPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = data.aws_ecr_repository.application.arn
      },
      {
        Sid      = "RuntimeSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.runtime.arn
      },
      {
        Sid      = "ConfigurationBucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = data.aws_s3_bucket.configuration.arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["environments/${var.environment}/*"]
          }
        }
      },
      {
        Sid      = "ConfigurationObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${data.aws_s3_bucket.configuration.arn}/environments/${var.environment}/*"
      },
      {
        Sid      = "RuntimeDatasetBuckets"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [for bucket in keys(var.runtime_s3_prefixes) : "arn:aws:s3:::${bucket}"]
        Condition = {
          StringLike = {
            "s3:prefix" = tolist(toset(flatten(values(var.runtime_s3_prefixes))))
          }
        }
      },
      {
        Sid    = "RuntimeDatasetObjects"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = flatten([
          for bucket, prefixes in var.runtime_s3_prefixes : [
            for prefix in prefixes : "arn:aws:s3:::${bucket}/${prefix}"
          ]
        ])
      },
      {
        Sid      = "RegistrationEmail"
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "arn:aws:ses:${var.region}:${var.aws_account_id}:identity/${var.ses_sender_identity}"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "instance" {
  name = "${var.environment}-rubber-duck"
  role = aws_iam_role.instance.name
}

locals {
  config_uri = "s3://${var.configuration_bucket}/environments/${var.environment}/config.yaml"
  scripts = {
    "/usr/local/sbin/instance-bootstrap.sh" = "${path.module}/../../scripts/instance-bootstrap.sh"
    "/usr/local/sbin/update-host.sh"        = "${path.module}/../../scripts/update-host.sh"
    "/usr/local/sbin/deploy-container.sh"   = "${path.module}/../../scripts/deploy-container.sh"
    "/usr/local/sbin/health-check.sh"       = "${path.module}/../../scripts/health-check.sh"
  }
  settings = {
    "/etc/rubber-duck/environment" = var.environment
    "/etc/rubber-duck/config-uri"  = local.config_uri
    "/etc/rubber-duck/secret-id"   = aws_secretsmanager_secret.runtime.name
    "/etc/rubber-duck/aws-region"  = var.region
  }
}

data "cloudinit_config" "instance" {
  gzip          = true
  base64_encode = true

  part {
    content_type = "text/cloud-config"
    content = yamlencode({
      write_files = concat(
        [for destination, source in local.scripts : {
          path        = destination
          owner       = "root:root"
          permissions = "0755"
          encoding    = "b64"
          content     = filebase64(source)
        }],
        [for destination, value in local.settings : {
          path        = destination
          owner       = "root:root"
          permissions = "0600"
          content     = "${value}\n"
        }]
      )
      runcmd = [["/usr/local/sbin/instance-bootstrap.sh", aws_ebs_volume.data.id]]
    })
  }
}

resource "aws_instance" "application" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.instance.name
  vpc_security_group_ids      = [aws_security_group.instance.id]
  user_data_base64            = data.cloudinit_config.instance.rendered
  user_data_replace_on_change = true

  metadata_options {
    http_endpoint               = "enabled"
    http_protocol_ipv6          = "disabled"
    http_put_response_hop_limit = 2
    http_tokens                 = "required"
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    delete_on_termination = true
    encrypted             = true
    volume_size           = var.root_volume_size_gib
    volume_type           = "gp3"
  }

  tags = {
    Name = "${var.environment}-rubber-duck"
  }

  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.current.account_id == var.aws_account_id
      error_message = "The active AWS account does not match aws_account_id."
    }
    precondition {
      condition     = data.aws_availability_zone.selected.region == var.region
      error_message = "The selected availability zone is not in the configured region."
    }
  }
}

resource "aws_volume_attachment" "data" {
  device_name = "/dev/sdf"
  instance_id = aws_instance.application.id
  volume_id   = aws_ebs_volume.data.id
}
