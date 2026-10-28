#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BOOTSTRAP_TF="$ROOT/aws/terraform/bootstrap"
ENVIRONMENT_TF="$ROOT/aws/terraform/environment"
TFVARS="$ENVIRONMENT_TF/environments/production.tfvars"
STATE_BUCKET=rubber-duck-terraform-state-844825014198
BOOTSTRAP_STATE_KEY=rubber-duck/bootstrap/terraform.tfstate
ACCOUNT_ID=844825014198
REGION=us-west-2
PROFILE=""
SECRETS_FILE=""
CONFIG_FILE=""

usage() {
  echo "usage: first-time-bootstrap.sh --profile AWS_PROFILE --secrets runtime.json --config config.yaml" >&2
}

while (($#)); do
  case "$1" in
    --profile)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      PROFILE=$2
      shift 2
      ;;
    --secrets)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      SECRETS_FILE=$2
      shift 2
      ;;
    --config)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      CONFIG_FILE=$2
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "unsupported option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

[[ -n $PROFILE && -f $SECRETS_FILE && -f $CONFIG_FILE ]] || {
  usage
  exit 2
}

for tool in aws jq terraform; do
  command -v "$tool" >/dev/null || {
    echo "missing required tool: $tool" >&2
    exit 127
  }
done

terraform_version=$(terraform version -json | jq -r .terraform_version)
version_floor=$(printf '%s\n' "1.10.0" "$terraform_version" | sort -V | head -n1)
[[ $version_floor == "1.10.0" ]] || {
  echo "Terraform 1.10.0 or newer is required; found $terraform_version" >&2
  exit 2
}

permissions=$(stat -c '%a' "$SECRETS_FILE" 2>/dev/null || stat -f '%Lp' "$SECRETS_FILE")
[[ $permissions =~ ^(400|600)$ ]] || {
  echo "runtime secret file must have mode 400 or 600" >&2
  exit 2
}

jq -e '
  type == "object" and
  (.OPENAI_API_KEY | type == "string" and length > 0) and
  (.DISCORD_TOKEN | type == "string" and length > 0) and
  (has("AWS_ACCESS_KEY_ID") | not) and
  (has("AWS_SECRET_ACCESS_KEY") | not) and
  (has("AWS_SESSION_TOKEN") | not) and
  all(to_entries[];
    (.key | test("^[A-Za-z_][A-Za-z0-9_]*$")) and
    (.value | type == "string") and
    (.value | test("[\\r\\n]") | not)
  )
' "$SECRETS_FILE" >/dev/null || {
  echo "runtime secret must contain OPENAI_API_KEY and DISCORD_TOKEN as single-line strings" >&2
  exit 2
}

unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN AWS_CONTAINER_CREDENTIALS_FULL_URI AWS_CONTAINER_CREDENTIALS_RELATIVE_URI AWS_REGION AWS_DEFAULT_REGION
export AWS_PROFILE=$PROFILE
export AWS_REGION=$REGION
export AWS_DEFAULT_REGION=$REGION
active_account=$(aws sts get-caller-identity --query Account --output text)
[[ $active_account == "$ACCOUNT_ID" ]] || {
  echo "AWS account mismatch: expected $ACCOUNT_ID, received $active_account" >&2
  exit 1
}

bucket_error=$(mktemp)
trap 'rm -f "$bucket_error"' EXIT
if aws s3api head-bucket --bucket "$STATE_BUCKET" 2>"$bucket_error"; then
  bucket_region=$(aws s3api get-bucket-location --bucket "$STATE_BUCKET" --query LocationConstraint --output text)
  [[ $bucket_region == "$REGION" ]] || {
    echo "state bucket is in unexpected region: $bucket_region" >&2
    exit 1
  }
elif grep -Eq '\(404\)|Not Found|NoSuchBucket' "$bucket_error"; then
  aws s3api create-bucket \
    --bucket "$STATE_BUCKET" \
    --region "$REGION" \
    --create-bucket-configuration "LocationConstraint=$REGION"
else
  echo "unable to inspect state bucket:" >&2
  cat "$bucket_error" >&2
  exit 1
fi
rm -f "$bucket_error"
trap - EXIT

terraform -chdir="$BOOTSTRAP_TF" init -input=false \
  -backend-config="bucket=$STATE_BUCKET" \
  -backend-config="key=$BOOTSTRAP_STATE_KEY" \
  -backend-config="region=$REGION" \
  -backend-config=use_lockfile=true \
  -backend-config=encrypt=true

managed() {
  terraform -chdir="$BOOTSTRAP_TF" state list | awk -v resource="$1" '$0 == resource { found = 1 } END { exit !found }'
}

for resource in aws_s3_bucket.state aws_s3_bucket_versioning.state aws_s3_bucket_server_side_encryption_configuration.state; do
  if ! managed "$resource"; then
    terraform -chdir="$BOOTSTRAP_TF" import \
      -input=false \
      -var="aws_account_id=$ACCOUNT_ID" \
      -var="region=$REGION" \
      -var="state_bucket=$STATE_BUCKET" \
      -var="permissions_boundary_arn=arn:aws:iam::$ACCOUNT_ID:policy/iamRolePermissionBoundary" \
      "$resource" "$STATE_BUCKET"
  fi
done
if ! managed aws_s3_bucket_public_access_block.state && \
  aws s3api get-public-access-block --bucket "$STATE_BUCKET" >/dev/null 2>&1; then
  terraform -chdir="$BOOTSTRAP_TF" import \
    -input=false \
    -var="aws_account_id=$ACCOUNT_ID" \
    -var="region=$REGION" \
    -var="state_bucket=$STATE_BUCKET" \
    -var="permissions_boundary_arn=arn:aws:iam::$ACCOUNT_ID:policy/iamRolePermissionBoundary" \
    aws_s3_bucket_public_access_block.state "$STATE_BUCKET"
fi

OIDC_ARN="arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
if ! managed aws_iam_openid_connect_provider.github && \
  aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
  terraform -chdir="$BOOTSTRAP_TF" import \
    -input=false \
    -var="aws_account_id=$ACCOUNT_ID" \
    -var="region=$REGION" \
    -var="state_bucket=$STATE_BUCKET" \
    -var="permissions_boundary_arn=arn:aws:iam::$ACCOUNT_ID:policy/iamRolePermissionBoundary" \
    aws_iam_openid_connect_provider.github "$OIDC_ARN"
fi

terraform -chdir="$BOOTSTRAP_TF" apply -input=false \
  -var="aws_account_id=$ACCOUNT_ID" \
  -var="region=$REGION" \
  -var="state_bucket=$STATE_BUCKET" \
  -var="permissions_boundary_arn=arn:aws:iam::$ACCOUNT_ID:policy/iamRolePermissionBoundary"

terraform -chdir="$ENVIRONMENT_TF" init -input=false \
  -backend-config="bucket=$STATE_BUCKET" \
  -backend-config="key=rubber-duck/environments/production/terraform.tfstate" \
  -backend-config="region=$REGION" \
  -backend-config=use_lockfile=true \
  -backend-config=encrypt=true

managed_environment() {
  terraform -chdir="$ENVIRONMENT_TF" state list | awk -v resource="$1" '$0 == resource { found = 1 } END { exit !found }'
}
if ! managed_environment aws_secretsmanager_secret.runtime && \
  aws secretsmanager describe-secret --secret-id /rubber-duck/production/runtime >/dev/null 2>&1; then
  terraform -chdir="$ENVIRONMENT_TF" import \
    -input=false \
    -var-file="$TFVARS" \
    aws_secretsmanager_secret.runtime /rubber-duck/production/runtime
fi

terraform -chdir="$ENVIRONMENT_TF" apply -input=false -var-file="$TFVARS"

secret_id=$(terraform -chdir="$ENVIRONMENT_TF" output -raw runtime_secret_name)
aws secretsmanager put-secret-value --secret-id "$secret_id" --secret-string "file://$SECRETS_FILE" >/dev/null
aws s3 cp "$CONFIG_FILE" "s3://rubber-duck-config/environments/production/config.yaml" \
  --sse AES256 \
  --only-show-errors

aws secretsmanager get-secret-value \
  --secret-id "$secret_id" \
  --version-stage AWSCURRENT \
  --query ARN \
  --output text >/dev/null
aws s3api head-object \
  --bucket rubber-duck-config \
  --key environments/production/config.yaml >/dev/null

printf 'bootstrap complete\nrole=%s\ninstance=%s\nsecret=%s\nconfiguration=%s\n' \
  "$(terraform -chdir="$BOOTSTRAP_TF" output -raw github_deploy_role_arn)" \
  "$(terraform -chdir="$ENVIRONMENT_TF" output -raw instance_id)" \
  "$secret_id" \
  "s3://rubber-duck-config/environments/production/config.yaml"
