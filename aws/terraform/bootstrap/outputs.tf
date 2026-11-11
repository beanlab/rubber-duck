output "github_deploy_role_arn" {
  description = "Role assumed by the production GitHub Actions workflow."
  value       = aws_iam_role.github_deploy.arn
}

output "state_bucket" {
  description = "Terraform state bucket name."
  value       = aws_s3_bucket.state.id
}
