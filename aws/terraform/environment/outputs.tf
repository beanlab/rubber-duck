output "environment" {
  value = var.environment
}

output "instance_id" {
  value = aws_instance.application.id
}

output "ami_id" {
  value = aws_instance.application.ami
}

output "volume_id" {
  value = aws_ebs_volume.data.id
}

output "runtime_secret_arn" {
  value = aws_secretsmanager_secret.runtime.arn
}

output "runtime_secret_name" {
  value = aws_secretsmanager_secret.runtime.name
}

output "configuration_uri" {
  value = local.config_uri
}

output "ecr_repository_uri" {
  value = data.aws_ecr_repository.application.repository_url
}
